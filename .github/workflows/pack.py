#Python Packer to extract / create XML files for CodeBase for Token Efficient AI Uplaods
import os
import fnmatch

def generate_tree(dir_path, ignore_dirs):
    tree_str = ""
    for root, dirs, files in os.walk(dir_path):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        level = root.replace(dir_path, '').count(os.sep)
        indent = ' ' * 4 * level
        tree_str += f"{indent}{os.path.basename(root)}/\n"
        sub_indent = ' ' * 4 * (level + 1)
        for f in files:
            tree_str += f"{sub_indent}{f}\n"
    return tree_str

def is_binary(file_path):
    try:
        with open(file_path, 'tr') as check_file:
            check_file.read(1024)
            return False
    except UnicodeDecodeError:
        return True

def pack_repo(source_dir, output_file):
    ignore_dirs = {'.git', 'node_modules', 'dist', '__pycache__', '.vscode', 'artifacts'}
    ignore_exts = {'.exe', '.dll', '.so', '.png', '.jpg', '.ico', '.pdf', '.zip', '.sum'}
    
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write("<project_structure>\n")
        out.write(generate_tree(source_dir, ignore_dirs))
        out.write("</project_structure>\n\n")
        
        out.write("<project_files>\n")
        
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                if any(file.endswith(ext) for ext in ignore_exts):
                    continue
                    
                file_path = os.path.join(root, file)
                if is_binary(file_path):
                    continue
                    
                rel_path = os.path.relpath(file_path, source_dir)
                
                out.write(f'<file path="{rel_path}">\n')
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        out.write(f.read())
                except Exception as e:
                    out.write(f"Error reading file: {e}")
                out.write(f'\n</file>\n\n')
                
        out.write("</project_files>\n")

if __name__ == "__main__":
    pack_repo(".", "gemini_context.xml")
    print("Codebase packed into gemini_context.xml")
