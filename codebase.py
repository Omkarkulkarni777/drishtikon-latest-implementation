import os
import re
import importlib.util
import pkgutil
# Usage:
# Start with pip list > requirements.txt
# Run the script using python3 codebase.py
# This creates a requirements_safe.txt file
# Finally, run mv requirements_safe.txt requirements after reviewing 
# requirements_safe.txt



def is_native_package(package_name):
    """
    Returns True if the installed package contains native extensions (.so, .pyd, .dll)
    Otherwise returns False.
    """
    try:
        spec = importlib.util.find_spec(package_name)
        if spec is None or not spec.submodule_search_locations:
            return False

        package_path = list(spec.submodule_search_locations)[0]

        for root, dirs, files in os.walk(package_path):
            for f in files:
                if f.endswith((".so", ".pyd", ".dll", ".dylib", ".c", ".cpp")):
                    return True
        return False

    except Exception:
        # If not detectable, default to pure python (safe guess)
        return False


def create_safe_requirements(pip_list_file):
    with open(pip_list_file, "r") as f:
        lines = f.readlines()

    # Skip the header (usually first 2 lines)
    cleaned = "".join(lines).split("\n")[2:]

    output = []

    for line in cleaned:
        parts = line.split()
        if len(parts) < 2:
            continue

        name, version = parts[0], parts[1]

        # Determine if the package is native
        if is_native_package(name):
            output.append(name)  # leave unpinned
        else:
            output.append(f"{name}=={version}")  # safe to pin

    # Write output to a new requirements file
    name, ext = os.path.splitext(pip_list_file)
    output_path = f"{name}_safe{ext}"

    with open(output_path, "w") as f:
        f.write("\n".join(output))

    print(f"Created Raspberry Pi safe requirements file: {output_path}")


# ---- RUN ----
if __name__ == "__main__":
    cwd = os.getcwd()
    requirements_file = os.path.join(cwd, "requirements.txt")  # your pip list dump
    create_safe_requirements(requirements_file)
