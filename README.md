# LaTeX Project Cleaner

## 1. Overview

`latex_cleaner.py` is a Python script designed to clean up and consolidate a multi-file LaTeX project into a single, self-contained directory. The goal is to create a clean, portable, and submission-ready version of your project by merging all `.tex` source files, removing unused definitions and bibliography entries, and copying only the necessary assets.

The script performs the following key actions:
* **Merges TeX Files**: Recursively processes `\input{}` and `\include{}` commands to merge all subsidiary `.tex` files into a single `main.tex`.
* **Removes Comments**: Strips out line comments (`%...`) and block comments (`\begin{comment}...\end{comment}`).     
* **Consolidates Preamble**: Finds all `\usepackage`, `\newcommand`, and `\definecolor` declarations, removes duplicates and unused definitions, and moves them to the preamble of the main `.tex` file.
* **Cleans Bibliography**: Creates a new `.bib` file containing only the entries that are actually cited (`\cite{...}`) in the document.
* **Copies Assets**: Identifies and copies all referenced assets, including images (`\includegraphics`), custom class files (`.cls`), and bibliography style files (`.bst`), into the new directory.
* **Reformats Code**: Cleans up and re-indents the final TeX code for better readability.

## 2. How to Use

You can run the script from your terminal.

### Command-Line Usage

```bash
python latex_cleaner.py [main_document] [options]
```

### Arguments

* `main_document`: (Required) The name of the root `.tex` file of your project (e.g., `main.tex`, `report.tex`).
* `-i, --input_dir`: (Optional) The path to the root directory of your LaTeX project. Defaults to the directory of `main_document`.    
* `-o, --output_dir`: (Optional) The path to the output directory where the clean project will be saved. Defaults to a new directory named `<input_dir>_clean`.

### Example

If your project is in a directory named `my_thesis` and your main file is `thesis.tex`, you can run the following command from inside the `my_thesis` directory:

```bash
python path/to/latex_cleaner.py thesis.tex -o my_thesis_submission
```

This will create a new directory `my_thesis_submission` containing the cleaned project.

## 3. Limitations and Important Warnings

This script relies on regular expressions for parsing and is not a full-fledged LaTeX compiler. Its capabilities are limited, and it may not work perfectly for all projects. Please read the following limitations and warnings carefully.

### ⚠️ 1. Limited Scope of Recognized Commands

The script is designed to recognize a finite set of commands and environments. Support for anything outside this scope is not guaranteed. This includes:
* **Definitions**: The script only consolidates `\usepackage`, `\newcommand`, `\renewcommand`, `\providecommand`, and `\definecolor`. Other custom definition commands will be ignored.
* **Bibliography Entries**: Only a limited set of standard BibTeX entry types (e.g., `@article`, `@book`, `@inproceedings`) are recognized for cleaning.
* **Protected Environments**: Formatting is preserved only within a predefined list of environments (e.g., `figure`, `table`, `equation`). Text in other custom environments may be reformatted incorrectly.

### ⚠️ 2. Potential Errors with Complex Structures

The script may fail or produce incorrect output when faced with highly complex or unconventional LaTeX code.
* **Nested Definitions**: Complicated nested commands or environments can confuse the parsing logic, leading to errors in the final output.

### ⚠️ 3. Incomplete Asset Detection

The script's ability to find and copy assets is not foolproof.
* **Implicitly Included Images**: Images included via complex custom commands or from within a class file (`.cls`) might not be detected.
* **Extensionless Image References**: The script may fail to find images that are referenced in `\includegraphics{}` commands without a file extension (e.g., `\includegraphics{my_figure}` instead of `\includegraphics{my_figure.pdf}`).

### ⚠️ 4. User Responsibility: Backup and Verify!

Given these limitations, it is critical that you take precautions before and after using this script.

* **ALWAYS BACKUP YOUR PROJECT**: Before running the script, create a complete backup of your original project. The script deletes the output directory if it already exists, so a mistake could lead to data loss.
* **UNDERSTAND THE SCRIPT**: It is strongly recommended that you read the source code to understand what it does before running it on your project.
* **VERIFY THE OUTPUT**: After the script finishes, thoroughly inspect the generated project. Compile the new `main.tex` file and carefully check the PDF for any errors, missing content, formatting issues, or missing figures. Ensure that all necessary files have been copied correctly.