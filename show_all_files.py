#!/usr/bin/env python3
"""
Script to display all file contents for easy copy-paste to GitHub
"""

import os

# Files to display
files_to_show = [
    'requirements.txt',
    'sfc_placement_framework.py', 
    'experimental_evaluation.py',
    'test_implementation.py',
    'quick_demo.py',
    'README.md',
    'IMPLEMENTATION_SUMMARY.md',
    '.gitignore',
    'GITHUB_SETUP_GUIDE.md'
]

def show_file_content(filename):
    """Display file content with clear separators"""
    print("=" * 80)
    print(f"FILE: {filename}")
    print("=" * 80)
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
            print(content)
    except FileNotFoundError:
        print(f"File {filename} not found!")
    except Exception as e:
        print(f"Error reading {filename}: {e}")
    
    print("\n" + "=" * 80)
    print(f"END OF FILE: {filename}")
    print("=" * 80 + "\n\n")

def main():
    print("SFC PLACEMENT FRAMEWORK - ALL FILE CONTENTS")
    print("=" * 80)
    print("Copy each section below to create the files in your local directory")
    print("=" * 80 + "\n")
    
    for filename in files_to_show:
        show_file_content(filename)
    
    print("INSTRUCTIONS:")
    print("1. Create a new folder for your project")
    print("2. For each file above, create a new file with the exact name")
    print("3. Copy the content between the separator lines")
    print("4. Save each file")
    print("5. Follow the GITHUB_SETUP_GUIDE.md to upload to GitHub")

if __name__ == "__main__":
    main()