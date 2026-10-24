import re
import uuid
import hashlib
from services.latex_renderer import render_latex_block_result
from services.question_policy import id6_question_type


_ALLOWED_PREAMBLE_PACKAGES = {
    "amsmath", "amssymb", "array", "booktabs", "caption", "colortbl",
    "diagbox", "forest", "graphicx", "longtable", "makecell", "mathtools",
    "multirow", "pgfplots", "siunitx", "subcaption", "tabularx", "tikz",
    "tkz-euclide", "xcolor",
}
_SAFE_PREAMBLE_COMMANDS = (
    r"\newcommand", r"\renewcommand", r"\providecommand",
    r"\newcolumntype", r"\definecolor", r"\colorlet",
    r"\tikzset", r"\pgfplotsset", r"\def",
)
_UNSAFE_TEX_TOKENS = (
    r"\input", r"\include", r"\openin", r"\openout", r"\read",
    r"\write", r"\immediate", r"\usepackage", r"\documentclass",
    r"\begin{document}", r"\end{document}",
)

_CURRICULUM_ID_PATTERN = re.compile(
    r'%\[\s*(?P<grade>\d{1,2})C(?P<chapter>\d+)'
    r'(?P<level>[NHVC])(?P<section>i)-(?P<category>\d+)'
    r'(?P<type>[TDS])(?:\.(?P<sequence>[1-9]\d*))?\s*\]',
    re.IGNORECASE,
)
_CURRICULUM_LEVELS = {
    "N": "nhan_biet",
    "H": "thong_hieu",
    "V": "van_dung",
    "C": "van_dung_cao",
}


def _strip_latex_comments(content):
    """Remove ordinary LaTeX comments while preserving ID annotations like %[9C8...]."""
    return re.sub(r'(?<!\\)%(?!\[).*$', '', content, flags=re.MULTILINE)


def _extract_curriculum_metadata(text, **kwargs):
    """Decode a Chapter 8 ID under the single standard (T=single, D=true_false, S=short_answer)."""
    matches = list(_CURRICULUM_ID_PATTERN.finditer(text or ""))
    if not matches:
        return {}
    match = matches[0]
    fingerprints = {
        (item.group("grade"), item.group("chapter"), item.group("level").upper(),
         item.group("section").lower(), item.group("category"), item.group("type").upper(),
         item.group("sequence"))
        for item in matches
    }
    if len(fingerprints) > 1:
        return {"id6_metadata_conflict": "Một câu có nhiều tiền tố ID6 khác nhau; cần giữ lại đúng một tiền tố trong file nguồn."}
    values = match.groupdict()
    level = values["level"].upper()
    section = "i"
    type_code = values["type"].upper()
    decoded_type = id6_question_type(type_code)
    if not decoded_type:
        return {"id6_metadata_conflict": "Tiền tố ID6 có loại câu không hợp lệ; chỉ nhận T, D, S."}
    prefix = f"{values['grade']}C{values['chapter']}{level}{section}-{values['category']}{type_code}"
    sequence = values.get("sequence")
    return {
        "source_id": prefix + (f".{int(sequence)}" if sequence else ""),
        "id6_prefix": prefix,
        "id6_sequence": int(sequence) if sequence else None,
        "grade": f"Lớp {values['grade']}",
        "chapter": values["chapter"],
        "section": section,
        "question_category": values["category"],
        "difficulty_level": _CURRICULUM_LEVELS[level],
        "question_type": decoded_type,
    }


def extract_curriculum_metadata_list(file_path, **kwargs):
    """Read only ID metadata from each question, preserving question order."""
    with open(file_path, 'r', encoding='utf-8') as handle:
        raw_content = handle.read()
    clean_content = _strip_latex_comments(raw_content)
    question_pattern = re.compile(
        r'\\begin\{(bt|ex|question|bai)\}(.*?)\\end\{\1\}',
        re.DOTALL | re.IGNORECASE,
    )
    return [
        _extract_curriculum_metadata(match.group(2))
        for match in question_pattern.finditer(clean_content)
    ]


def _format_latex_lists(text):
    """Convert enumerate and itemize blocks in question body to readable formatted lines with labels."""
    if not text:
        return text

    def replace_enum(match):
        opt = match.group(1) or ''
        body = match.group(2)
        opt_clean = opt.strip()

        prefix_type = '1.'
        if '(a)' in opt_clean or '(A)' in opt_clean:
            prefix_type = '(a)'
        elif 'a)' in opt_clean or 'A)' in opt_clean:
            prefix_type = 'a)'
        elif '(1)' in opt_clean:
            prefix_type = '(1)'
        elif '1)' in opt_clean:
            prefix_type = '1)'
        elif 'i)' in opt_clean or '(i)' in opt_clean:
            prefix_type = '(i)'

        items = re.findall(r'\\item(?:\s*\[(?!\[)([^]]*)\])?\s*(.*?)(?=\\item|$)', body, re.DOTALL | re.IGNORECASE)
        formatted_items = []
        for idx, (custom_lbl, itext) in enumerate(items):
            itext = itext.strip()
            if not itext:
                continue
            if custom_lbl:
                lbl = custom_lbl.strip()
            elif prefix_type == '(a)':
                lbl = f'({chr(97 + idx)})'
            elif prefix_type == 'a)':
                lbl = f'{chr(97 + idx)})'
            elif prefix_type == '(1)':
                lbl = f'({idx + 1})'
            elif prefix_type == '1)':
                lbl = f'{idx + 1})'
            elif prefix_type == '(i)':
                roman = ['i', 'ii', 'iii', 'iv', 'v', 'vi'][idx] if idx < 6 else f'{idx+1}'
                lbl = f'({roman})'
            else:
                lbl = f'{idx + 1}.'
            formatted_items.append(f'{lbl} {itext}')
        return '\n' + '\n'.join(formatted_items) + '\n'

    def replace_item(match):
        body = match.group(1)
        items = re.findall(r'\\item(?:\s*\[(?!\[)([^]]*)\])?\s*(.*?)(?=\\item|$)', body, re.DOTALL | re.IGNORECASE)
        formatted = []
        for custom_lbl, itext in items:
            itext = itext.strip()
            if not itext:
                continue
            lbl = custom_lbl.strip() if custom_lbl else '•'
            formatted.append(f'{lbl} {itext}')
        return '\n' + '\n'.join(formatted) + '\n'

    text = re.sub(r'\\begin\{enumerate\}(?:\[(?!\[)([^]]*)\])?(.*?)\\end\{enumerate\}', replace_enum, text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'\\begin\{itemize\}(.*?)\\end\{itemize\}', replace_item, text, flags=re.DOTALL | re.IGNORECASE)
    return text


def parse_latex(file_path, **kwargs):
    r"""
    Parse LaTeX (.tex, .latex) files to extract questions.
    Supports:
    1. Standard text formats (Câu 1:, A. B. C. D.)
    2. LaTeX environments (\begin{ex} ... \end{ex}, \choice)
    """
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        raw_content = f.read()

    clean_content = _strip_latex_comments(raw_content)
    safe_preamble = _extract_safe_preamble(clean_content)

    raw_questions = []
    ex_pattern = re.compile(
        r'\\begin\{(bt|ex|question|bai)\}(.*?)\\end\{\1\}',
        re.DOTALL | re.IGNORECASE,
    )
    matches = list(ex_pattern.finditer(clean_content))
    
    if matches:
        for match in matches:
            raw_q_text = match.group(2).strip()
            curriculum_metadata = _extract_curriculum_metadata(raw_q_text)
            q_text = _unwrap_immini(re.sub(r'(?<!\\)%.*$', '', raw_q_text, flags=re.MULTILINE).strip())
            section_prefix = clean_content[:match.start()].lower()
            section_markers = [
                (section_prefix.rfind(r"\cauds"), "true_false"),
                (section_prefix.rfind(r"\caukq"), "short_answer"),
                (section_prefix.rfind(r"\cautl"), "short_answer"),
                (section_prefix.rfind(r"\caulc"), "single"),
            ]
            marker_position, section_type = max(section_markers, key=lambda item: item[0])
            if marker_position < 0:
                # Files often use command-based structures without a section
                # declaration. The former max(-1) tie selected true/false
                # for every such question.
                section_type = "single"
            options = []
            statements = []

            # Extract \loigiai before parsing answers so explanation content
            # is not mistaken for question body or answer choices.
            solution_match = _extract_command_arguments(q_text, r'loigiai')
            if solution_match:
                statement_part = q_text[:solution_match[0]].strip()
                solution_part = solution_match[1][0]
            elif re.search(r'\\loigiai\s*', q_text, re.IGNORECASE):
                # Preserve a useful fallback for malformed templates while
                # preferring balanced argument parsing for normal files.
                statement_part, solution_part = re.split(
                    r'\\loigiai\s*', q_text, maxsplit=1, flags=re.IGNORECASE
                )
                statement_part = statement_part.strip()
            else:
                statement_part, solution_part = q_text, ''

            # ex_test uses command-based structures (\choice, \choiceTF, \shortans).
            # Parse braced arguments with nesting support because formulas
            # commonly contain commands such as \dfrac{a}{b}.
            choice_tf = _extract_command_arguments(statement_part, r'choiceTF')
            choice = _extract_command_arguments(statement_part, r'choice')
            short_answer = _extract_command_arguments(statement_part, r'shortans')
            shortans_source = 'statement'

            if not short_answer and solution_part:
                sol_short = _extract_command_arguments(solution_part, r'shortans')
                if sol_short:
                    short_answer = sol_short
                    shortans_source = 'solution'
                    solution_part = (solution_part[:sol_short[0]] + " " + solution_part[sol_short[2]:]).strip()

            if not short_answer:
                q_short = _extract_command_arguments(q_text, r'shortans')
                if q_short:
                    short_answer = q_short
                    shortans_source = 'q_text'

            if choice_tf:
                q_text = statement_part[:choice_tf[0]].strip()
                for i, opt_text in enumerate(choice_tf[1]):
                    is_correct, opt_text = _extract_answer_marker(opt_text)
                    statements.append({
                        "id": chr(97 + i),
                        "text": opt_text,
                        "answer": is_correct,
                    })
            elif choice:
                q_text = statement_part[:choice[0]].strip()
                for i, opt_text in enumerate(choice[1]):
                    is_correct, opt_text = _extract_answer_marker(opt_text)
                    options.append({
                        "letter": chr(65 + i),
                        "text": opt_text,
                        "is_correct": is_correct,
                        "order_index": i,
                    })
            elif short_answer:
                if shortans_source == 'statement':
                    q_text = (statement_part[:short_answer[0]] + " " + statement_part[short_answer[2]:]).strip()
                elif shortans_source == 'solution':
                    q_text = statement_part.strip()
                else:
                    q_text = statement_part.strip()

                raw_ans = short_answer[1][0].strip()
                # Unwrap math delimiters if wrapping simple text or numbers: $25$ -> 25
                m_math = re.match(r'^(?:\$|\\\()(.*?)(?:\$|\\\))$', raw_ans, re.DOTALL)
                if m_math:
                    inner = m_math.group(1).strip()
                    if not re.search(r'\\(?:frac|dfrac|sqrt|sum|int|begin)\b', inner):
                        raw_ans = inner

                answer = _clean_latex_text(raw_ans)
                from services.question_policy import clean_latex_math_to_text
                answer = clean_latex_math_to_text(answer) or answer
                options.append({
                    "letter": "A",
                    "text": answer,
                    "is_correct": True,
                    "order_index": 0,
                })
            else:
                q_text = statement_part.strip()
                # Fallback 1: Plain text options (A. B. C. D.)
                # In the short-answer and legacy tự luận sections, labels such as
                # ``a)`` are sub-questions, not multiple-choice options.
                if section_type != "short_answer":
                    opt_pattern = re.compile(
                        r'(?:^|\s+)(A|B|C|D)[\.\:\)]\s+(.*?)(?=(?:\s+(?:A|B|C|D)[\.\:\)]\s+|$))',
                        re.IGNORECASE | re.DOTALL,
                    )
                    opt_matches = opt_pattern.findall(q_text)
                    if opt_matches:
                        for i, (letter, opt_text) in enumerate(opt_matches):
                            options.append({
                                "letter": letter.upper(),
                                "text": opt_text.strip(),
                                "is_correct": False,
                                "order_index": i,
                            })
                        # Remove options from q_text
                        first_option = re.search(r'(?:^|\s+)(?:A|B|C|D)[\.\:\)]\s+', q_text, re.IGNORECASE)
                        q_text = q_text[:first_option.start()].strip() if first_option else q_text

                # Fallback 2: True/False statements from \begin{enumerate}
                # ONLY if no options were found AND this is explicitly True/False
                if not options and (
                    section_type == "true_false" or
                    curriculum_metadata.get("question_type") == "true_false"
                ):
                    enum_match = re.search(
                        r'\\begin\{enumerate\}(.*?)\\end\{enumerate\}',
                        q_text,
                        re.DOTALL | re.IGNORECASE,
                    )
                    if enum_match:
                        before_enum = q_text[:enum_match.start()].strip()
                        item_source = enum_match.group(1)
                        item_matches = re.findall(
                            r'\\item(?:\s*\[[^]]*\])?\s*(.*?)(?=\\item|$)',
                            item_source,
                            re.DOTALL | re.IGNORECASE,
                        )
                        item_matches = [item.strip() for item in item_matches if item.strip()]
                        if item_matches:
                            q_text = before_enum
                            for idx, item_text in enumerate(item_matches):
                                is_correct, clean_item = _extract_answer_marker(item_text)
                                statements.append({
                                    "id": chr(97 + idx),
                                    "text": clean_item,
                                    "answer": is_correct if ("\\True" in item_text or "\\False" in item_text) else None,
                                })

            # Format lists inside question text to preserve item labels (a), (b), (c), (d)
            q_text = _format_latex_lists(q_text)

            if choice_tf:
                inferred_type = "true_false"
            elif choice:
                inferred_type = "single"
            elif short_answer:
                inferred_type = "short_answer"
            elif statements:
                inferred_type = "true_false"
            elif options:
                inferred_type = "single"
            elif section_type == "short_answer":
                inferred_type = "short_answer"
            else:
                inferred_type = section_type

            sample_ans = options[0]["text"] if (inferred_type == "short_answer" and options) else ""
            raw_question = {
                "source_label": f"Khối {len(raw_questions)+1} — dòng {raw_content.count(chr(10),0,match.start())+1}",
                "question_text": q_text,
                "context": "",
                "question_type": inferred_type,
                "difficulty_level": curriculum_metadata.get("difficulty_level", ""),
                "explanation": solution_part.strip(),
                "options": options,
                "statements": statements,
                "raw_correct": sample_ans,
                "sample_answer": sample_ans,
                "image_url": "",
                "formulas": {},
                "confidence_scores": {
                    "question": 0.9,
                    "type": 0.9,
                    "image": 1.0,
                    "answer": 0.8
                }
            }
            # Keep parser-detected answer structure authoritative.  The ID
            # metadata adapter validates the type later; it must not silently
            # turn a ``\choice`` into TF merely because a tag says ``T``.
            raw_question.update({key: value for key, value in curriculum_metadata.items()
                                 if key != "question_type"})
            raw_questions.append(raw_question)
    else:
        # Fallback to plain text parsing line by line
        lines = clean_content.split('\n')
        current_q = None
        q_num_pattern = re.compile(r'^(?:Câu|Bài|Ví dụ)\s*(\d+)\s*[.\:)\-]*\s*(.*)', re.IGNORECASE)
        opt_pattern = re.compile(r"^(['’'*]?)\s*(?:\[|\()?([A-E])[.:)\-\]\】]\s*(.*)")
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            q_match = q_num_pattern.match(line)
            if q_match:
                if current_q:
                    raw_questions.append(current_q)
                current_q = {
                    "question_text": q_match.group(2),
                    "source_label": f"Câu {q_match.group(1)} (mục {len(raw_questions)+1})",
                    "context": "",
                    "question_type": "single",
                    "difficulty_level": "",
                    "explanation": "",
                    "options": [],
                    "statements": [],
                    "raw_correct": "",
                    "image_url": "",
                    "formulas": {},
                    "confidence_scores": {
                        "question": 0.8,
                        "type": 0.8,
                        "image": 1.0,
                        "answer": 0.7
                    }
                }
                continue
                
            opt_match = opt_pattern.match(line)
            if opt_match and current_q:
                prefix = opt_match.group(1)
                letter = opt_match.group(2).upper()
                opt_text = opt_match.group(3).strip()
                is_corr = bool(prefix in ("'", "’", "*"))
                if opt_text.endswith("*"):
                    opt_text = opt_text[:-1].strip()
                    is_corr = True
                    
                current_q["options"].append({
                    "letter": letter,
                    "text": opt_text,
                    "is_correct": is_corr,
                    "order_index": len(current_q["options"])
                })
                continue
                
            if current_q and not current_q["options"]:
                current_q["question_text"] += "\n" + line
                
        if current_q:
            raw_questions.append(current_q)

    # Plain comment labels and section headings work for every grade/topic.
    # They are metadata, never commands or instructions to execute.
    metadata_content = re.sub(r'(?<!\\)%(?!\[|\s*@(?:grade|category|level)\s*:).*$', '', raw_content, flags=re.MULTILINE)
    original_blocks = list(ex_pattern.finditer(metadata_content))
    if len(original_blocks) == len(raw_questions):
        for question, block in zip(raw_questions, original_blocks):
            question['classification_evidence'] = 'source_id' if question.get('source_id') else ''
            prefix = metadata_content[:block.start()]
            local = block.group(2)
            explicit_category = False
            for key, field in (('grade', 'grade'), ('category', 'question_category'), ('level', 'difficulty_level')):
                pattern = r'(?m)^\s*%\s*@' + key + r'\s*:\s*([^\r\n]+)'
                values = re.findall(pattern, local) or re.findall(pattern, prefix)
                if values and not question.get('source_id'):
                    question[field] = values[-1].strip()
                    if key == 'category':
                        explicit_category = True
                        question['classification_evidence'] = 'category'
            if not explicit_category and not str(question.get('source_id', '')).startswith('9C8'):
                headings = re.findall(r'\\section\*?\{([^{}]+)\}', prefix)
                from services.latex_document import knowledge_heading
                if headings and knowledge_heading(headings[-1]):
                    question['question_category'] = headings[-1].strip()
                    question['classification_evidence'] = 'heading'
                elif question.get('question_category'):
                    question['question_category'] = 'Dạng ' + question['question_category']
            if not question.get('difficulty_level'):
                levels = re.findall(r'\\subsection\*?\{([^{}]+)\}', prefix)
                if levels:
                    from services.question_normalizer import normalize_difficulty
                    level_heading = re.sub(r'^\s*(?:[IVX]+|\d+)\s*[.):–-]\s*', '', levels[-1], flags=re.I)
                    question['difficulty_level'] = normalize_difficulty(level_heading)

    # Post-process every user-visible field, including true/false statements
    # and explanations.  Previously only question_text and options were
    # processed, so formulas inside \item were left as raw LaTeX.
    for q in raw_questions:
        q["question_text"] = _extract_assets(_unwrap_immini(q["question_text"]), q["formulas"], safe_preamble)
        q["question_text"] = _clean_latex_text(_extract_formulas(q["question_text"], q["formulas"]))
        if q.get("question_type") == "short_answer":
            for opt in q["options"]:
                txt = opt["text"].strip()
                from services.question_policy import clean_latex_math_to_text
                cleaned = clean_latex_math_to_text(_clean_latex_text(txt))
                opt["text"] = cleaned or _clean_latex_text(txt).strip()
            if q.get("options"):
                q["sample_answer"] = q["options"][0]["text"]
                q["raw_correct"] = q["options"][0]["text"]
        else:
            for opt in q["options"]:
                opt["text"] = _clean_latex_text(_extract_formulas(_extract_assets(opt["text"], q["formulas"], safe_preamble), q["formulas"]))
        for stmt in q["statements"]:
            stmt["text"] = _clean_latex_text(_extract_formulas(_extract_assets(stmt["text"], q["formulas"], safe_preamble), q["formulas"]))
        q["context"] = _clean_latex_text(_extract_formulas(_extract_assets(q.get("context", ""), q["formulas"], safe_preamble), q["formulas"]))
        q["explanation"] = _process_explanation(
            q.get("explanation", ""), q["formulas"], safe_preamble
        )

    return raw_questions

def _extract_formulas(text, formulas_dict):
    """
    Extract LaTeX math mode $...$ and $$...$$ into FormulaAsset placeholders.
    """
    if not text:
        return text
        
    # Process longest/multiline delimiters first.  ``ch_thucte_12.tex`` uses
    # both inline ``$...$`` and display ``\[...\]`` math.
    pattern = re.compile(
        r'(\$\$(.*?)\$\$|\\\[(.*?)\\\]|\\\((.*?)\\\)|'
        r'\\begin\{(equation\*?|align\*?|gather\*?|multline\*?)\}(.*?)'
        r'\\end\{\5\}|\$(.*?)\$)',
        re.DOTALL,
    )
    
    def replacer(match):
        groups = match.groups()
        # Groups 2, 3, 4 are the standard delimiters. For equation-like
        # environments, group 5 contains the body; group 4 is only the
        # environment name. The final group is `$...$`.
        latex_content = next(
            (groups[index] for index in (1, 2, 3, 5, 6) if groups[index] is not None),
            '',
        )
        latex_content = latex_content.strip()
        # A display wrapper around a figure is layout, not a second formula.
        if re.fullmatch(r"\[\[formula:[a-f0-9-]+\]\]", latex_content):
            return latex_content


        # MathJax receives the extracted body without its original display
        # environment.  Alignment tabs are invalid at top level and surface
        # as "Misplaced &" unless we restore an alignment container.
        environment = groups[4]
        if environment and environment.lower().startswith('align'):
            latex_content = r'\begin{aligned}' + latex_content + r'\end{aligned}'
        elif '&' in latex_content:
            latex_content = r'\begin{aligned}' + latex_content + r'\end{aligned}'
        
        if not latex_content:
            return match.group(0)
            
        f_id = str(uuid.uuid4())
        formulas_dict[f_id] = {
            "latex": latex_content,
            "source_format": "LaTeX",
            "needs_review": False,
            "content_hash": hashlib.sha256(latex_content.encode("utf-8")).hexdigest(),
            "conversion_status": "converted",
            "parse_confidence": 1.0,
        }
        return f" [[formula:{f_id}]] "

    return pattern.sub(replacer, text)


def _process_explanation(text, formulas_dict, preamble=""):
    """Normalize solution-only layout macros before frontend rendering."""
    if not text:
        return text
    text = _unwrap_immini(text)
    text = _extract_assets(text, formulas_dict, preamble)
    text = _extract_formulas(text, formulas_dict)
    text = _format_latex_lists(text)
    text = _clean_latex_text(text)
    # At this point math and image blocks are placeholders, so remaining
    # double backslashes are prose line breaks rather than equation rows.
    text = re.sub(r'\\\\(?:\[[^]]*\])?', '\n', text)
    return text.strip()


def _unwrap_immini(text):
    r"""Replace ``\immini{text}{visual}`` with its two visible arguments."""
    command_pattern = re.compile(r'\\immini\b(?:\s*\[[^]]*\])?', re.IGNORECASE)
    cursor = 0
    output = []
    while True:
        match = command_pattern.search(text, cursor)
        if not match:
            output.append(text[cursor:])
            break
        output.append(text[cursor:match.start()])
        parsed = _read_braced_arguments(text, match.end(), limit=2)
        if not parsed or len(parsed[0]) < 2:
            output.append(text[match.start():match.end()])
            cursor = match.end()
            continue
        arguments, end_pos = parsed
        answer = re.search(r'\\(?:choiceTF|choice|shortans)\b', arguments[0])
        if answer:
            # The diagram belongs to the stem even when answers are in the left column.
            output.append(arguments[0][:answer.start()] + '\n' + arguments[1] + '\n' + arguments[0][answer.start():])
        else:
            output.append(arguments[0] + '\n' + arguments[1])
        cursor = end_pos
    return ''.join(output)


def _read_braced_arguments(text, position, limit=None):
    """Read balanced braced arguments beginning at ``position``."""
    pos = position
    arguments = []
    while pos < len(text) and (limit is None or len(arguments) < limit):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text) or text[pos] != '{':
            break
        start = pos + 1
        depth = 1
        pos += 1
        while pos < len(text) and depth:
            if text[pos] == '\\':
                pos += 2
                continue
            if pos < len(text) and text[pos] == '{':
                depth += 1
            elif pos < len(text) and text[pos] == '}':
                depth -= 1
            pos += 1
        if depth:
            return None
        arguments.append(text[start:pos - 1])
    return (arguments, pos) if arguments else None


def _extract_command_arguments(text, command):
    """Extract all braced arguments from an ex_test command.

    Returns ``(start_index, arguments, end_index)`` or ``None``. This intentionally
    parses balanced braces instead of using ``[^}]`` so nested LaTeX works.
    Supports optional bracket arguments like \\choice[2] or \\choiceTF[t].
    """
    match = re.search(r'\\' + command + r'\b(?:\s*\[[^]]*\])?', text, re.IGNORECASE)
    if not match:
        return None
    parsed = _read_braced_arguments(text, match.end())
    return (match.start(), parsed[0], parsed[1]) if parsed else None


def _extract_answer_marker(text):
    """Return ``(is_correct, text_without_marker)`` for ex_test choices."""
    is_correct = bool(re.search(r'\\True\b', text, re.IGNORECASE))
    text = re.sub(r'\\(?:True|False)\b\s*', '', text, flags=re.IGNORECASE)
    return is_correct, text.strip()


def clean_latex_quotes(text):
    """Normalize LaTeX quotation marks (\\lq, \\rq, \\textquotedbl..., ``...'') to standard Unicode quotes."""
    if not text:
        return text
    # 1. LaTeX double quotes macros
    text = re.sub(r'\\lq\s*\\lq(?:\{\}|\\[ \t]+|\s*)?', '“', text)
    text = re.sub(r'\\rq\s*\\rq(?:\{\}|\\[ \t]+)', '” ', text)
    text = re.sub(r'\\rq\s*\\rq', '”', text)

    # 2. LaTeX quote commands
    text = re.sub(r'\\textquotedblleft(?:\{\}|\\[ \t]+|\s*)?', '“', text)
    text = re.sub(r'\\textquotedblright(?:\{\}|\\[ \t]+)', '” ', text)
    text = re.sub(r'\\textquotedblright', '”', text)
    text = re.sub(r'\\textquotedbl(?:\{\}|\\[ \t]+|\s*)?', '"', text)

    # 3. LaTeX single quotes macros
    text = re.sub(r'\\lq(?:\{\}|\\[ \t]+|\s*)?', '‘', text)
    text = re.sub(r'\\rq(?:\{\}|\\[ \t]+)', '’ ', text)
    text = re.sub(r'\\rq', '’', text)
    text = re.sub(r'\\textquoteleft(?:\{\}|\\[ \t]+|\s*)?', '‘', text)
    text = re.sub(r'\\textquoteright(?:\{\}|\\[ \t]+)', '’ ', text)
    text = re.sub(r'\\textquoteright', '’', text)

    # 4. TeX ligature quotes: ``word'' -> “word”
    text = re.sub(r'``', '“', text)
    text = re.sub(r"''", '”', text)

    # 5. Spacing normalization around quotes
    text = re.sub(r'\s+([”’])', r'\1', text)
    text = re.sub(r'([“‘])\s+', r'\1', text)
    text = re.sub(r'([”’"])([\w])', r'\1 \2', text)
    text = re.sub(r'([\w])([“‘"])', r'\1 \2', text)
    text = re.sub(r'\\[ \t]+', ' ', text)
    return text


def _clean_latex_text(text):
    """Remove presentation-only LaTeX constructs before MathJax render."""
    if not text:
        return text

    # Layout directives have no prose meaning. Math and blocks are already protected.
    text = re.sub(r'\\(?:renewcommand|setlength)\s*\{\s*\\(?:arraystretch|tabcolsep|extrarowheight)\s*\}\s*\{[^{}]*\}', '', text)
    text = re.sub(r'\\(?:small|footnotesize|scriptsize|tiny|normalsize|large|Large|LARGE|huge|Huge|centering)\b', '', text)
    text = re.sub(r'\\definecolor\s*\{[^{}]*\}\s*\{[^{}]*\}\s*\{[^{}]*\}', '', text)
    # Convert LaTeX quotes to standard quotes first
    text = clean_latex_quotes(text)

    # Keep the text inside structural environments but remove their wrappers.
    text = re.sub(
        r'\\(?:begin|end)\{(?:center|flushleft|flushright|itemize|enumerate|itemchoice|tcolorbox|minipage)\}(?:\[[^]]*\])?',
        '', text, flags=re.IGNORECASE,
    )
    text = re.sub(r'\\itemch?\s*', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'\\(?:item|noindent|par|quad|qquad|hspace|vspace)(?:\{[^{}]*\}|\[[^]]*\])?\s*', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'\\text\{([^{}]*)\}', r'\1', text)
    text = re.sub(r'\\(?:textbf|textit|textrm|textsf|emph)\{([^{}]*)\}', r'\1', text)
    text = re.sub(r'\\(?:left|right)\b', '', text)
    text = re.sub(r'\\(?:,|;|:|!)', ' ', text)
    text = re.sub(r'\\(?:label|tag)\{[^{}]*\}', '', text)
    return re.sub(r'[ \t]+', ' ', text).strip()


def _extract_safe_preamble(content):
    """Keep only renderer-relevant, non-I/O declarations from a TeX preamble."""
    document_start = re.search(r"\\begin\{document\}", content, re.IGNORECASE)
    first_question = re.search(r"\\begin\{(?:ex|bt|question|bai)\}", content)
    boundary = document_start.start() if document_start else first_question.start() if first_question else 50_000
    preamble = content[:boundary]
    kept = []

    package_pattern = re.compile(
        r"\\usepackage(?:\[[^]]*\])?\{([^{}]+)\}", re.IGNORECASE
    )
    for match in package_pattern.finditer(preamble):
        packages = [name.strip() for name in match.group(1).split(",")]
        allowed = [name for name in packages if name.lower() in _ALLOWED_PREAMBLE_PACKAGES]
        if allowed:
            kept.append(r"\usepackage{" + ",".join(allowed) + "}")

    for command in (r"\usetikzlibrary", r"\usepgfplotslibrary"):
        pattern = re.compile(re.escape(command) + r"\{([a-zA-Z0-9,._-]+)\}")
        kept.extend(match.group(0) for match in pattern.finditer(preamble))

    # Custom definitions are accepted only when they fit on one line and do
    # not contain file/process I/O primitives. The renderer repeats this
    # validation because API input must never trust the parser alone.
    for raw_line in preamble.splitlines():
        line = raw_line.strip()
        if not line.startswith(_SAFE_PREAMBLE_COMMANDS):
            continue
        lowered = line.lower()
        if line.count('{') == line.count('}') and len(line) <= 2000 and not any(token.lower() in lowered for token in _UNSAFE_TEX_TOKENS):
            kept.append(line)

    # Stable order makes the asset hash and renderer cache deterministic.
    return "\n".join(kept)


def _extract_assets(text, formulas_dict, preamble=""):
    """Replace non-MathJax LaTeX blocks by server-rendered SVG assets."""
    if not text:
        return text

    block_names = {
        "tikzpicture", "tikz", "pgfpicture", "pspicture",
        "tabular", "tabular*", "tabularx", "longtable",
        "picture", "verbatim", "lstlisting",
    }
    begin_pattern = re.compile(r'\\begin\{([^}]+)\}|\\tikz\b(?:\s*\[[^]]*\])?', re.IGNORECASE)

    def replace_source(source, local_preamble=""):
        block_preamble = "\n".join(filter(None, [preamble, local_preamble]))
        from services.tex_table import parse_table
        table = parse_table(source)
        render_result = ({'verified': True, 'method': 'structured_table_v1'} if table
                         else render_latex_block_result(source, preamble=block_preamble))
        url = render_result.get("url")
        verified = bool(render_result.get("verified"))
        asset_id = str(uuid.uuid4())
        hash_payload = f"{block_preamble}\n%__QUESTION_BLOCK__%\n{source}"
        formulas_dict[asset_id] = {
            "latex": None,
            "mathml": None,
            "source_text": source,
            "source_preamble": block_preamble,
            "source_format": "LaTeXBlock",
            "conversion_status": "converted" if table else "fallback_svg" if url else "failed",
            "table": table,
            "verification_status": "verified" if verified else "needs_review",
            "needs_review": not verified,
            "preview_url": url,
            "svg_cache_key": url,
            "render_method": render_result.get("method"),
            "render_error": render_result.get("error"),
            "content_hash": hashlib.sha256(hash_payload.encode("utf-8")).hexdigest(),
            "parse_confidence": 1.0 if verified else (0.5 if url else 0.0),
        }
        return f" [[formula:{asset_id}]] "

    # Regex with a non-greedy body breaks nested tabular environments. Walk
    # the source and match begin/end pairs by depth instead. Keep scanning
    # after unrelated environments, since a question often contains an
    # enumerate before its table or TikZ figure.
    output = []
    cursor = 0
    while cursor < len(text):
        match = begin_pattern.search(text, cursor)
        if not match:
            output.append(text[cursor:])
            break
        if match.group(1) is None:
            parsed = _read_braced_arguments(text, match.end(), limit=1)
            if parsed:
                output.append(text[cursor:match.start()])
                output.append(replace_source(text[match.start():parsed[1]], _extract_safe_preamble(text[:match.start()])))
                cursor = parsed[1]
            else:
                output.append(text[cursor:match.end()])
                cursor = match.end()
            continue
        env_name = match.group(1).lower()
        if env_name not in block_names:
            output.append(text[cursor:match.end()])
            cursor = match.end()
            continue
        output.append(text[cursor:match.start()])
        depth = 1
        scan = match.end()
        closing_start = None
        closing_end = None
        token_pattern = re.compile(r'\\(?:begin|end)\{([^}]+)\}', re.IGNORECASE)
        for token in token_pattern.finditer(text, scan):
            token_name = token.group(1).lower()
            if token_name != env_name:
                continue
            if token.group(0).lower().startswith('\\begin'):
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    closing_start, closing_end = token.start(), token.end()
                    break
        if closing_end is None:
            # Preserve malformed source for the caller to review.
            output.append(text[match.start():])
            break
        output.append(replace_source(text[match.start():closing_end], _extract_safe_preamble(text[:match.start()])))
        cursor = closing_end
    return ''.join(output)


def normalize_question_latex(question):
    """Use the same rendering pipeline after uploads and teacher edits."""
    formulas = question.setdefault('formulas', {})
    def normalize(text):
        for asset_id in formulas:
            text = re.sub(r'(?<!\[)\[formula:' + re.escape(asset_id) + r'\s*\](?!\])',
                          '[[formula:' + asset_id + ']]', text or '')
        return _process_explanation(text or '', formulas)
    for field in ('question_text', 'context', 'explanation'):
        question[field] = normalize(question.get(field, ''))
    items = question.get('statements', [])
    if question.get('question_type') != 'short_answer':
        items = items + question.get('options', [])
    for item in items:
        item['text'] = normalize(item.get('text', ''))
    return question
