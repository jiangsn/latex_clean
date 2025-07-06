# latex_cleaner.py

import os
import re
import shutil
import argparse
from pathlib import Path


def find_project_root(start_path, main_doc_name):
    """
    Searches upward from a starting path to locate the project root directory
    containing the main .tex file.

    Args:
        start_path (str): The directory path to start the search from.
        main_doc_name (str): The name of the main .tex file to find.

    Returns:
        Path: The Path object of the project root if found, otherwise None.
    """
    current_path = Path(start_path).resolve()
    while not (current_path / main_doc_name).exists():
        if current_path.parent == current_path:  # Reached the filesystem root
            return None
        current_path = current_path.parent
    return current_path


def merge_tex_files(tex_file_path, project_root, processed_files):
    r"""
    Recursively merges .tex files referenced by \input{} or \include{} commands.

    During the merge, this function removes line and block comments while
    preventing infinite recursion.

    Args:
        tex_file_path (Path): Path to the current .tex file being processed.
        project_root (Path): The root directory of the LaTeX project.
        processed_files (set): A set of file paths that have already been
                               processed, to prevent circular references.

    Returns:
        str: The content of the file after merging and comment removal.
    """
    if tex_file_path in processed_files:
        return f"% --- SKIPPING RECURSIVE INCLUDE OF {tex_file_path.name} ---\n"
    processed_files.add(tex_file_path)

    try:
        with open(tex_file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return f"% --- FILE NOT FOUND: {tex_file_path} ---\n"
    except Exception as e:
        return f"% --- ERROR READING FILE: {tex_file_path}, {e} ---\n"

    # Define regex for comment removal
    RE_BLOCK_COMMENT = re.compile(
        r"\\begin\s*\{\s*comment\s*\}.*?\\end\s*\{\s*comment\s*\}\s*\n?", re.DOTALL
    )
    RE_LINE_COMMENT = re.compile(r"(?<!\\)%.*(?:\n|$)")

    # Remove comments before processing inputs
    content_no_comments = RE_LINE_COMMENT.sub("", content)
    content_no_comments = RE_BLOCK_COMMENT.sub("", content_no_comments)

    def replace_input(match):
        r"""Helper function to process each \input or \include command."""
        included_filename = match.group(1)
        if not included_filename.endswith(".tex"):
            included_filename += ".tex"

        # Check for the file relative to the current file, then relative to the project root
        included_file_path_relative = tex_file_path.parent / included_filename
        included_file_path_root = project_root / included_filename
        final_path = (
            included_file_path_relative
            if included_file_path_relative.exists()
            else included_file_path_root
        )

        if final_path.exists():
            print(f"    - Merging: {final_path.relative_to(project_root)}")
            return merge_tex_files(final_path, project_root, processed_files)
        else:
            print(f"    - WARNING: Included file not found: '{included_filename}'")
            return f"% --- INCLUDED FILE NOT FOUND: {included_filename} ---\n"

    RE_INPUT = re.compile(r"\\(?:input|include)\s*\{\s*(.*?)\s*\}")
    return RE_INPUT.sub(replace_input, content_no_comments)


def clean_tex_content(content):
    r"""
    Cleans and reformats the merged TeX content.

    This function performs the following operations:
    1. Removes leading indentation from each line.
    2. Normalizes multiple consecutive blank lines into a single one.
    3. Merges paragraphs outside of protected environments (like figure, table)
       into single lines.
    4. Specifically handles the \caption{} command, merging its content into a
       single line.

    Args:
        content (str): The TeX content to be cleaned.

    Returns:
        str: The cleaned and formatted TeX content.
    """
    PROTECTED_ENVIRONMENTS = [
        "figure",
        "figure*",
        "table",
        "table*",
        "tabular",
        "verbatim",
        "Verbatim",
        "lstlisting",
        "equation",
        "equation*",
        "align",
        "align*",
        "itemize",
        "enumerate",
        "description",
    ]
    RE_PROTECTED_BLOCKS = re.compile(
        r"(\\begin\s*\{\s*(?:"
        + "|".join(PROTECTED_ENVIRONMENTS)
        + r")\s*\}.*?\\end\s*\{\s*(?:"
        + "|".join(PROTECTED_ENVIRONMENTS)
        + r")\s*\})",
        re.DOTALL,
    )
    RE_CAPTION = re.compile(r"(\\caption(?:\[.*?\])?\s*\{)\s*(.*?)\s*(\})", re.DOTALL)

    print("  - Removing leading indentation from all lines.")
    lines = [line.lstrip() for line in content.split("\n")]
    content = "\n".join(lines)

    print("  - Normalizing blank lines.")
    content = re.sub(r"\n\s*\n", "\n\n", content)
    content = re.sub(r"(\n\n)+", "\n\n", content)

    print("  - Reformatting paragraphs and captions.")
    parts = RE_PROTECTED_BLOCKS.split(content)
    processed_parts = []
    RE_MERGE_LINES = re.compile(r"(?<!\n)\n(?![\\\n])")

    def process_caption_content(match):
        """Collapses newlines within a caption to a single space."""
        opening, caption_text, closing = match.group(1), match.group(2), match.group(3)
        processed_text = RE_MERGE_LINES.sub(" ", caption_text)
        processed_text = re.sub(r" +", " ", processed_text).strip()
        return f"{opening}{processed_text}{closing}"

    for i, part in enumerate(parts):
        if i % 2 == 1:  # This is a protected block
            processed_block = RE_CAPTION.sub(process_caption_content, part)
            processed_parts.append(processed_block)
        else:  # This is regular text
            part = RE_MERGE_LINES.sub(" ", part)
            part = re.sub(r" +", " ", part)
            processed_parts.append(part)

    return "".join(processed_parts)


def _find_balanced_braces(text, start_index):
    """
    A helper function to find the position of a matching right brace, starting
    from a given left brace.

    Args:
        text (str): The string to search within.
        start_index (int): The index of the opening left brace '{'.

    Returns:
        int: The index of the matching right brace '}', or -1 if not found.
    """
    if start_index >= len(text) or text[start_index] != "{":
        return -1
    brace_level = 1
    for i in range(start_index + 1, len(text)):
        char = text[i]
        if char == "{":
            brace_level += 1
        elif char == "}":
            brace_level -= 1
        if brace_level == 0:
            return i
    return -1


def _extract_packages(content):
    r"""
    Extracts all \usepackage declarations from the TeX content.

    It deduplicates them and sorts them alphabetically by package name.

    Args:
        content (str): The TeX content from which to extract packages.

    Returns:
        tuple[list[str], list[tuple[int, int]]]:
            - A list of sorted, unique \usepackage commands.
            - A list of tuples containing the start and end indices of the
              original declarations in the text.
    """
    RE_USEPACKAGE_CMD = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{[^\}]+\}")
    RE_PKG_NAME_EXTRACTOR = re.compile(r"\\usepackage(?:\[.*?\])?\{([^\}]+)\}")

    all_coords = []
    declarations = {}  # Use dict to store command -> package_name for sorting

    for match in re.finditer(RE_USEPACKAGE_CMD, content):
        command_text = match.group(0)
        name_match = RE_PKG_NAME_EXTRACTOR.search(command_text)
        if name_match:
            # Handle packages like {pkg1, pkg2} by using the first one for sorting
            package_name = name_match.group(1).split(",")[0].strip()
            declarations[command_text] = package_name
            all_coords.append((match.start(), match.end()))

    if not declarations:
        return [], []

    # Sort the unique commands based on their primary package name
    sorted_commands = sorted(declarations.keys(), key=lambda cmd: declarations[cmd])

    print(f"  - Found {len(all_coords)} total \\usepackage commands.")
    print(f"  - Keeping {len(sorted_commands)} unique \\usepackage commands:")
    for cmd in sorted_commands:
        print(f"    - {cmd}")

    return sorted_commands, all_coords


def _extract_definitions(content, def_type):
    """
    A helper function to extract all macro definitions (like newcommand) or
    color definitions (definecolor).

    This function only keeps definitions that are used in the document
    (occurrence count > 1, where the definition itself counts as one).

    Args:
        content (str): The TeX content to search within.
        def_type (str): 'command' or 'color'.

    Returns:
        tuple[dict, list]:
            - A dictionary mapping the names of used definitions to their full text.
            - A list of tuples containing the start and end indices of all
              original definitions in the text.
    """
    if def_type == "command":
        RE_DEF_HEAD = re.compile(
            r"\\(?:renew|new|provide)command\s*\*?\s*\{\s*\\(\w+)\s*\}((?:\[[^\]]*\]){0,2})\s*(\{)",
            re.DOTALL,
        )
        usage_pattern = r"\\"
    elif def_type == "color":
        RE_DEF_HEAD = re.compile(
            r"\\definecolor\s*\{\s*(\w+)\s*\}\s*\{\s*(\w+)\s*\}\s*(\{)"
        )
        usage_pattern = r"\b"
    else:
        return {}, []

    all_definitions = []
    for head_match in re.finditer(RE_DEF_HEAD, content):
        name = head_match.group(1)
        body_start_index = head_match.start(3)
        body_end_index = _find_balanced_braces(content, body_start_index)

        if body_end_index != -1:
            def_start = head_match.start()
            def_end = body_end_index + 1
            full_text = content[def_start:def_end]
            all_definitions.append(
                {"name": name, "text": full_text, "start": def_start, "end": def_end}
            )

    if not all_definitions:
        print(f"  - Found no {def_type} definitions.")
        return {}, []

    used_definitions_map = {}
    print(
        f"  - Found {len(all_definitions)} total {def_type} definitions. Checking usage..."
    )
    for defi in all_definitions:
        name = defi["name"]
        re_usage = re.compile(usage_pattern + name + r"\b")
        # The definition itself counts as one usage. We keep if used anywhere else.
        count = len(re_usage.findall(content))
        if count > 1:
            used_definitions_map[name] = defi["text"]

    print(f"  - Keeping {len(used_definitions_map)} used {def_type} definitions:")
    for name, text in sorted(used_definitions_map.items()):
        print(f"    - {text.splitlines()[0]}")

    all_coords = [(d["start"], d["end"]) for d in all_definitions]
    return used_definitions_map, all_coords


def process_preamble_and_definitions(content):
    r"""
    Analyzes, extracts, and moves all necessary definitions (packages, macros,
    colors) to after the \documentclass declaration.

    This function removes all original definition declarations and then inserts
    the deduplicated, sorted, and used declarations into the correct position
    in the document preamble.

    Args:
        content (str): The complete, merged TeX content.

    Returns:
        str: The TeX content with a reorganized preamble.
    """
    RE_DOC_CLASS = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{[^\}]+?\}")

    print("  - Analyzing \\usepackage, \\newcommand, and \\definecolor declarations.")
    sorted_packages, package_coords = _extract_packages(content)
    used_commands, command_coords = _extract_definitions(content, "command")
    used_colors, color_coords = _extract_definitions(content, "color")

    # Surgically remove ALL definitions from original content first.
    # We iterate backwards to not mess up the indices of earlier parts of the string.
    all_coords = package_coords + command_coords + color_coords
    all_coords.sort(key=lambda x: x[0], reverse=True)

    content_list = list(content)
    for start, end in all_coords:
        # Also remove preceding whitespace to avoid empty lines
        while start > 0 and content_list[start - 1].isspace():
            start -= 1
        del content_list[start:end]

    body_content = "".join(content_list)

    # Create the full preamble block to be inserted.
    preamble_parts = []
    if sorted_packages:
        preamble_parts.append("\n".join(sorted_packages))
    if used_commands:
        # Sort commands alphabetically by name for consistency
        sorted_command_names = sorted(used_commands.keys())
        preamble_parts.append(
            "\n".join([used_commands[name] for name in sorted_command_names])
        )
    if used_colors:
        # Sort colors alphabetically by name
        sorted_color_names = sorted(used_colors.keys())
        preamble_parts.append(
            "\n".join([used_colors[name] for name in sorted_color_names])
        )

    full_preamble_block = "\n\n".join(filter(None, preamble_parts))

    # Find insertion point and assemble the final content.
    doc_class_match = RE_DOC_CLASS.search(body_content)

    if doc_class_match and full_preamble_block:
        print("  - Inserting cleaned preamble after \\documentclass.")
        insertion_point = doc_class_match.end()
        final_content = (
            body_content[:insertion_point]
            + "\n\n"
            + full_preamble_block
            + body_content[insertion_point:]
        )
    elif full_preamble_block:
        print(
            "  - WARNING: \\documentclass not found. Placing definitions at the top of the file."
        )
        final_content = full_preamble_block + "\n\n" + body_content
    else:
        print("  - No preamble definitions to move.")
        final_content = body_content

    return final_content


def reindent_tex_content(content):
    r"""
    Re-applies standard indentation to the cleaned TeX code to improve
    readability.

    It tracks indentation levels using `\begin` and `\end` commands.

    Args:
        content (str): The TeX content to be re-indented.

    Returns:
        str: The beautified TeX code with indentation.
    """
    print("  - Applying standard indentation to the final TeX code.")
    lines = content.split("\n")
    indented_lines = []
    indent_level = 0
    indent_str = "    "  # 4 spaces for one indent level

    RE_INDENT = re.compile(r"\\begin\s*\{|\\left\b")
    RE_DEDENT = re.compile(r"\\end\s*\{|\\right\b")

    for line in lines:
        line = line.strip()
        if not line:
            indented_lines.append("")
            continue

        # For lines starting with \end or \right, dedent before printing the line
        is_dedent_first = line.startswith("\\end") or line.startswith("\\right")

        indent_delta = len(RE_INDENT.findall(line)) - len(RE_DEDENT.findall(line))

        # A special case for the document environment to not be indented
        if re.match(r"\\begin\s*\{\s*document\s*\}", line):
            indent_delta -= 1

        if is_dedent_first:
            indent_level = max(0, indent_level + indent_delta)
            indented_lines.append(indent_str * indent_level + line)
        else:
            indented_lines.append(indent_str * indent_level + line)
            indent_level = max(0, indent_level + indent_delta)

    return "\n".join(indented_lines)


def clean_bib_file(bib_path, used_citations, output_dir):
    r"""
    Cleans a .bib file to include only entries that are actually cited in the
    .tex document.

    It preserves all @string macros and writes the cleaned content to a new
    `main.bib` file.

    Args:
        bib_path (Path): Path to the original .bib file.
        used_citations (set): A set of all `\cite{}` keys used in the document.
        output_dir (Path): The output directory where the new .bib file will be
                           saved.

    Returns:
        str: The name of the new .bib file if created successfully, otherwise None.
    """
    if not bib_path.exists():
        print(f"  - WARNING: Bibliography file not found: {bib_path}")
        return None

    print(f"  - Processing bibliography: {bib_path.name}")
    with open(bib_path, "r", encoding="utf-8") as f:
        bib_content = f.read()

    # Preserve @string macros, which are often used for journal abbreviations
    string_macros = re.findall(
        r"(@string\s*\{.*?\})", bib_content, re.IGNORECASE | re.DOTALL
    )
    if string_macros:
        print(f"  - Found and preserving {len(string_macros)} @string macro(s).")

    # A robust regex to find BibTeX entries
    BIB_ENTRY_TYPES = [
        "article",
        "book",
        "inproceedings",
        "phdthesis",
        "mastersthesis",
        "inbook",
        "incollection",
        "proceedings",
        "techreport",
        "unpublished",
        "misc",
    ]
    RE_ENTRY = re.compile(
        r"(@(?:" + "|".join(BIB_ENTRY_TYPES) + r"))\s*\{([^,]+),.*?\n\}",
        re.IGNORECASE | re.DOTALL,
    )
    RE_LINE_COMMENT = re.compile(r"(?<!\\)%.*(?:\n|$)")

    kept_entries_text = []
    all_entry_keys = []
    print(
        f"  - Filtering entries based on {len(used_citations)} unique citation keys..."
    )
    for entry_match in re.finditer(RE_ENTRY, bib_content):
        entry_key = entry_match.group(2).strip()
        all_entry_keys.append(entry_key)
        if entry_key in used_citations:
            print(f"    - Keeping entry: {entry_key}")
            kept_entries_text.append(entry_match.group(0))

    if not kept_entries_text and not string_macros:
        print(
            "  - WARNING: No cited entries or @string macros found. No .bib file will be created."
        )
        return None

    final_bib_parts = []
    if string_macros:
        final_bib_parts.extend(string_macros)
    if kept_entries_text:
        final_bib_parts.extend(kept_entries_text)
    clean_content = "\n\n".join(final_bib_parts)

    # Remove comments from the final content
    uncommented_lines = [
        RE_LINE_COMMENT.sub("", line).rstrip() for line in clean_content.split("\n")
    ]
    clean_content = "\n".join(uncommented_lines)
    clean_content = re.sub(r"\n\s*\n", "\n\n", clean_content)  # Normalize blank lines

    output_bib_name = "main.bib"
    output_bib_path = output_dir / output_bib_name
    with open(output_bib_path, "w", encoding="utf-8") as f:
        f.write(clean_content.strip())
    print(
        f"  - Successfully created clean bibliography '{output_bib_name}' with {len(kept_entries_text)} entries."
    )
    return output_bib_name


def main():
    """The main function, which parses command-line arguments and executes the cleaning process in order."""
    parser = argparse.ArgumentParser(
        description="Clean a LaTeX project into a single, self-contained .tex file and a directory with necessary assets.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "main_document", help="The main .tex file of the project (e.g., 'main.tex')."
    )
    parser.add_argument(
        "-i",
        "--input_dir",
        default=".",
        help="The root directory of the LaTeX project (default: current directory).",
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        default=None,
        help="The directory for the clean project (default: 'input_dir_name_clean').",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    main_document_name = args.main_document
    main_document_path = input_dir / main_document_name

    if not main_document_path.exists():
        print(
            f"Main document '{main_document_name}' not found in '{input_dir}'. Searching upwards..."
        )
        project_root = find_project_root(Path(".").resolve(), main_document_name)
        if not project_root:
            print(
                f"ERROR: Cannot find '{main_document_name}'. Please specify the correct input directory with -i."
            )
            return
        input_dir = project_root
        main_document_path = input_dir / main_document_name
        print(f"Found project root at: {input_dir}")

    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else input_dir.with_name(input_dir.name + "_clean")
    )

    # Check that input and output directories are not the same
    if output_dir == input_dir:
        print("ERROR: The output directory cannot be the same as the input directory.")
        print("Please specify a different output directory with the -o flag.")
        return

    if output_dir.exists():
        print(f"Output directory '{output_dir}' already exists. Removing it...")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    print(f"Created clean output directory: {output_dir}\n")

    # --- Step 1: Merge .tex files and remove comments ---
    print(f"[Step 1/7] Merging TeX files and removing comments...")
    processed_files = set()
    merged_content = merge_tex_files(main_document_path, input_dir, processed_files)

    # --- Step 2: Relocate preamble definitions ---
    print("\n[Step 2/7] Processing preamble and definitions...")
    relocated_content = process_preamble_and_definitions(merged_content)

    # --- Step 3: Reformat paragraphs and layout ---
    print("\n[Step 3/7] Reformatting the merged TeX content...")
    clean_content = clean_tex_content(relocated_content)

    # --- Step 4: Re-indent final TeX code ---
    print("\n[Step 4/7] Re-indenting the final TeX code...")
    final_tex_content = reindent_tex_content(clean_content)

    # --- Step 5: Handling class and style files (.cls, .bst) ---
    print("\n[Step 5/7] Handling class and style files (.cls, .bst)...")
    RE_DOC_CLASS = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{([^\}]+)\}")
    RE_BIBSTYLE = re.compile(r"\\bibliographystyle\s*\{\s*(.*?)\s*\}")
    custom_cls_path = None  # Variable to store the path to a custom .cls file

    # .cls handling
    doc_class_match = RE_DOC_CLASS.search(final_tex_content)
    if doc_class_match:
        class_name = doc_class_match.group(1).strip()
        cls_filename = class_name + ".cls"
        src_cls_path = input_dir / cls_filename
        if src_cls_path.exists():
            shutil.copy2(src_cls_path, output_dir / cls_filename)
            print(f"  - Copied custom class file: '{cls_filename}'")
            custom_cls_path = src_cls_path  # Store path for image search later
        else:
            print(
                f"  - Using standard class '{class_name}'. No .cls file found in project root."
            )
    else:
        print("  - WARNING: No \\documentclass found. Cannot check for a .cls file.")

    # .bst handling
    bst_match = RE_BIBSTYLE.search(final_tex_content)
    if bst_match:
        bst_filename = bst_match.group(1) + ".bst"
        src_bst_path = input_dir / bst_filename
        if src_bst_path.exists():
            shutil.copy2(src_bst_path, output_dir / bst_filename)
            print(f"  - Copied bibliography style file: '{bst_filename}'")
        else:
            print(
                f"  - WARNING: Bibliography style file '{bst_filename}' not found in project root."
            )

    # --- Step 6: Handling bibliography data (.bib) ---
    print("\n[Step 6/7] Handling bibliography data (.bib)...")
    RE_CITE = re.compile(r"\\cite(?:\[.*?\])?\s*\{(.*?)\}")
    RE_BIBLIOGRAPHY = re.compile(r"\\bibliography\s*\{\s*(.*?)\s*\}")
    all_citations = {
        k.strip()
        for match in RE_CITE.finditer(final_tex_content)
        for k in match.group(1).split(",")
    }

    bib_match = RE_BIBLIOGRAPHY.search(final_tex_content)
    if bib_match and all_citations:
        bib_names = [b.strip() for b in bib_match.group(1).split(",")]
        new_bib_name = None
        for bib_name in bib_names:
            src_bib_path = input_dir / (bib_name + ".bib")
            if src_bib_path.exists():
                # Clean the first bib file found and stop
                new_bib_name = clean_bib_file(src_bib_path, all_citations, output_dir)
                break

        if new_bib_name:
            new_bib_cmd = r"\\bibliography{" + Path(new_bib_name).stem + "}"
            final_tex_content = RE_BIBLIOGRAPHY.sub(new_bib_cmd, final_tex_content)
            print(f"  - Updated \\bibliography command to use '{new_bib_name}'.")
    elif not bib_match:
        print("  - No \\bibliography command found. Skipping .bib processing.")
    else:  # bib_match exists but no citations found
        print("  - No \\cite commands found. Skipping .bib processing.")

    # --- Step 7: Copying used image files ---
    print("\n[Step 7/7] Copying used image files...")
    RE_INCLUDEGFX = re.compile(r"\\includegraphics(?:\[.*?\])?\s*\{\s*(.*?)\s*\}")
    image_paths = set(RE_INCLUDEGFX.findall(final_tex_content))

    if custom_cls_path:
        print(
            f"  - Searching for images in custom class file: '{custom_cls_path.name}'..."
        )
        try:
            with open(custom_cls_path, "r", encoding="utf-8") as f:
                cls_content = f.read()
            cls_image_paths = set(RE_INCLUDEGFX.findall(cls_content))

            if cls_image_paths:
                initial_count = len(image_paths)
                image_paths.update(cls_image_paths)
                new_images_count = len(image_paths) - initial_count
                if new_images_count > 0:
                    print(
                        f"    - Found {new_images_count} additional unique image(s) in the class file."
                    )
            else:
                print(f"    - No new images found in the class file.")
        except Exception as e:
            print(
                f"    - WARNING: Could not read or parse '{custom_cls_path.name}'. Error: {e}"
            )

    print(f"  - Found {len(image_paths)} unique images to copy.")
    copied_count = 0
    for img_path_str in sorted(list(image_paths)):  # Sort for deterministic output
        src_img_path = input_dir / Path(img_path_str)
        if src_img_path.exists():
            dest_img_path = output_dir / Path(img_path_str)
            dest_img_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_img_path, dest_img_path)
            print(f"    - Copied: {img_path_str}")
            copied_count += 1
        else:
            print(f"  - WARNING: Image file not found: '{img_path_str}'")
    print(f"  - Successfully copied {copied_count} image files.")

    # --- Final Write ---
    output_tex_name = "main.tex"
    output_tex_path = output_dir / output_tex_name
    with open(output_tex_path, "w", encoding="utf-8") as f:
        f.write(final_tex_content)

    print(f"\n✅ Success! Clean project created at: '{output_dir}'")
    print(f"   - Main TeX file: '{output_tex_name}'")


if __name__ == "__main__":
    main()