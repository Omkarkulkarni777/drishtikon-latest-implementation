import os
import argparse
from pathspec import PathSpec

def create_requirements(file):
    with open(file, 'r') as fileObject:
        lines = fileObject.readlines()
        cleaned = "".join(lines).split('\n')[2:]
        res_list = []
        for line in cleaned:
            res = ''
            space_enc = False
            for char in line:
                if not char.strip():
                    if not space_enc:
                        res += "=="
                    space_enc = True
                    continue
                res += char
            res_list.append(res)

    outputFilepath = 'requirements.txt'
    with open(outputFilepath, 'w') as fileObj:
        fileObj.writelines("\n".join(res_list))

# pytree.py

def load_gitignore(base_path):
    """
    Load .gitignore from base_path and return a PathSpec matcher.
    If no .gitignore exists, return None.
    """
    gitignore_path = os.path.join(base_path, ".gitignore")
    if not os.path.exists(gitignore_path):
        return None

    with open(gitignore_path, "r") as f:
        patterns = f.read().splitlines()

    return PathSpec.from_lines("gitwildmatch", patterns)


def is_ignored(path, base_path, spec):
    """
    Check whether a path should be ignored based on the PathSpec rules.
    Path must be made relative to repo root for gitignore matching.
    """
    if spec is None:
        return False

    rel = os.path.relpath(path, base_path)
    return spec.match_file(rel)


def print_children(entity, level=0, entity_array=None, counter_array=None,
                   want_basenames=1, base_path=None, gitignore_spec=None):
    # Base path should be the root of traversal (level 0 initial path)
    if base_path is None:
        base_path = os.path.abspath(entity)
        gitignore_spec = load_gitignore(base_path)

    # Skip ignored files/folders
    if is_ignored(entity, base_path, gitignore_spec):
        return

    # Always skip the .git directory
    if os.path.isdir(entity) and os.path.basename(entity) == ".git" :
        return
    
    # Always skip the __pycache__ directory
    if os.path.isdir(entity) and os.path.basename(entity) == "__pycache__" :
        return


    # Initialize arrays
    if entity_array is None:
        entity_array = {}
    if counter_array is None:
        counter_array = {}

    if level not in entity_array:
        entity_array[level] = []
    entity_array[level].append(entity)

    if level not in counter_array:
        counter_array[level] = [0, 0]  # [folders, files]

    if os.path.isdir(entity):
        counter_array[level][0] += 1
        for local_entity in os.listdir(entity):
            local_entity_path = os.path.join(entity, local_entity)
            print_children(local_entity_path, level + 1,
                           entity_array, counter_array,
                           want_basenames, base_path, gitignore_spec)
    else:
        counter_array[level][1] += 1

    # Pretty-printing only at the very end
    if level == 0:
        for key in sorted(entity_array.keys()):
            print(f"{key}:")
            for ent in entity_array[key]:
                indent = "\t" * key
                symbol = "📁" if os.path.isdir(ent) else "📄"
                if want_basenames:
                    print(f"{indent}├── {symbol} {os.path.basename(ent)}")
                else:
                    print(f"{indent}├── {symbol} {ent}")
            print()

        print("📊 Summary:")
        for key in sorted(counter_array.keys()):
            folders, files = counter_array[key]
            print(f"Level {key}: Folders={folders}, Files={files}")


def build_tree_dict(path):
    node = {
        "path": path,
        "name": os.path.basename(path),
        "type": "folder" if os.path.isdir(path) else "file"
    }

    if os.path.isdir(path):
        node["children"] = [
            build_tree_dict(os.path.join(path, entry))
            for entry in os.listdir(path)
        ]

    return node

def tree_to_markdown(node, level=0):
    lines = []
    indent = "  " * level
    prefix = "- " if level else "# "
    lines.append(f"{indent}{prefix}{node['name']}")
    for child in node.get("children", []):
        lines.extend(tree_to_markdown(child, level + 1))
    return lines



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize directory structure like `tree`.")
    parser.add_argument("path", nargs="?", default=".", help="Directory path (default: current directory)")
    parser.add_argument("--basenames", action="store_true", help="Show basenames instead of absolute paths")
    parser.add_argument("--format", choices=["tree", "json", "markdown"], default="tree", help="Output format: tree (default), json, or markdown.")

    args = parser.parse_args()

    root_path = os.path.abspath(args.path)
    basenames = bool(args.basenames)


    if not os.path.exists(root_path):
        print("❌ Error: Path does not exist.", root_path)
    elif args.format == "tree":
        print_children(root_path, want_basenames=basenames)
    
    elif args.format == "json":
        import json
        tree = build_tree_dict(root_path)
        print(json.dumps(tree, indent=2))

    elif args.format == "markdown":
        tree = build_tree_dict(root_path)
        markdown_lines = tree_to_markdown(tree)
        print("\n".join(markdown_lines))

    create_requirements(os.path.join(os.getcwd(), 'requirements.txt'))