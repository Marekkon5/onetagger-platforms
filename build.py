import os
import sys
import toml
import json
import shutil
import github
import platform
import jsonschema
import subprocess

REPO = 'Marekkon5/onetagger-platforms'
GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
RELEASE_TAG = 'platforms'

def main():
    # Login to GitHub
    auth = github.Auth.Token(GITHUB_TOKEN)
    gh = github.Github(auth=auth)
    repo = gh.get_repo(REPO)
    release = repo.get_release(RELEASE_TAG)

    # Load all platforms
    platforms = json.load(open('platforms.json'))

    for folder in os.listdir('platforms'):
        platform = load_platform(os.path.join('platforms', folder))
        language = 'rust' if os.path.exists(os.path.join('platforms', folder, 'Cargo.toml')) else 'python'

        # Existing or update
        matched = list(filter(lambda i: i['id'] == platform['id'], platforms))
        if not (len(matched) == 0 or compare_versions(platform['version'], matched[0]['version']) == 1):
            continue

        # Skip python builds in non-final build
        if (language == 'rust' and '--python' not in sys.argv) or (language == 'python' and '--python' in sys.argv):
            print(f'Building {platform["id"]}', file=sys.stderr)

            # Build and upload
            artifact = build_platform(os.path.join('platforms', folder))
            release.upload_asset(artifact, os.path.basename(artifact), 'application/octet-stream')

        # Add new to manifest
        if len(matched) == 0:
            platforms.append({
                'id': platform['id'],
                'name': platform['name'],
                'description': platform['description'],
                'maxThreads': platform['maxThreads'],
                'requiresAuth': platform['requiresAuth'],
                'language': language,
                'author': platform['author'],
                'versions': {
                    platform['version']: platform['supportedVersion']
                },
                'version': platform['version']
            })
        # Update
        else:
            i = platforms.index(matched[0])
            platforms[i]['versions'].update({ platform['version']: platform['supportedVersion'] })
            platforms[i]['version'] = platform['version']

    # Save
    with open('platforms.json', 'w') as f:
        f.write(json.dumps(platforms, ensure_ascii=False, indent=4))

    # Commit
    if '--commit' in sys.argv:
        data = open('platforms.json', 'rb').read()
        contents = repo.get_contents('platforms.json')
        repo.update_file('platforms.json', '[CI] Update platforms.json', data, contents.sha, 'master')

# Compile and package platform, returns artifact path
def build_platform(path):
    # Create dist folder
    if not os.path.exists('dist'):
        os.makedirs('dist')

    # Load info
    info = json.load(open(os.path.join(path, 'info.json')))

    # Rust
    if 'Cargo.toml' in os.listdir(path):
        # Compile
        cwd = os.getcwd()
        os.chdir(path)
        subprocess.check_call(['cargo', 'update'])
        subprocess.check_call(['cargo', 'build', '--release'])
        os.chdir(cwd)

        # Copy output
        cargo = toml.loads(open(os.path.join(path, 'Cargo.toml')).read())
        name = cargo['package']['name'].replace('-', '_')
        output = os.path.join('dist', f'{info["id"]}_{info["version"]}')

        if platform.system() == 'Linux':
            name = f'lib{name}.so'
            output = f'{output}_linux_{platform.machine()}.so'
        if platform.system() == 'Darwin':
            name = f'lib{name}.dylib'
            output = f'{output}_macos_{platform.machine()}.dylib'
        if platform.system() == 'Windows':
            name = f'{name}.dll'
            output = f'{output}_windows_{platform.machine().replace("AMD64", "x86_64")}.dll'

        shutil.copy(os.path.join(path, 'target', 'release', name), output)
        return output
    

    # Python
    output = os.path.join('dist', f'{info["id"]}_{info["version"]}.zip')
    subprocess.check_call(['git', 'archive', '-o', output, f'HEAD:platforms/{info["id"]}'])
    return output


# Load data and verify schema
def load_platform(path):
    schema = {
        "type": "object",
        "properties": {
            "id": { "type": "string" },
            "name": { "type": "string" },
            "version": { "type": "string" },
            "description": { "type": "string" },
            "maxThreads": { "type": "number" },
            "requiresAuth": { "type": "boolean" },
            "supportedVersion": { "type": "number" },
            "author": { "type": "string" }
        }
    }
    data = json.load(open(os.path.join(path, 'info.json')))
    jsonschema.validate(instance=data, schema=schema)
    return data

# Compare 2 versions
def compare_versions(a, b):
    a = tuple(map(int, (a.split('.'))))
    b = tuple(map(int, (b.split('.'))))
    if len(a) == 2:
        a = (a[0], a[1], 0)
    if len(b) == 2:
        b = (b[0], b[1], 0)
    if a > b:
        return 1
    if a < b:
        return -1
    return 0



if __name__ == '__main__':
    main()