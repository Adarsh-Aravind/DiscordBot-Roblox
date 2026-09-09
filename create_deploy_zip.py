import glob
import zipfile
import os

# Root modules that must never ship: this packaging script itself.
EXCLUDE_ROOT_FILES = {'create_deploy_zip.py'}

def create_zip():
    exclude_dirs = {'__pycache__', 'venv', '.git'}
    # Every root-level module is collected automatically. Listing them by hand
    # meant a newly added module (modlog.py) silently missed the zip and the
    # deployed bot died on import.
    # NOTE: never bundle .env here -- it holds DISCORD_TOKEN. Copy it to the
    # target machine out of band (see .env.example for the required keys).
    files_to_include = sorted(
        f for f in glob.glob('*.py') if f not in EXCLUDE_ROOT_FILES
    ) + ['requirements.txt']

    with zipfile.ZipFile('Bit_Bot_Deploy.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add root files
        for file in files_to_include:
            if os.path.exists(file):
                zipf.write(file)
                print(f"Added {file}")
        
        # Add cogs directory
        for root, dirs, files in os.walk('cogs'):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    zipf.write(file_path)
                    print(f"Added {file_path}")

if __name__ == "__main__":
    create_zip()
