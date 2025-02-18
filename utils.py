import re
import json
import difflib
import html


# ----------------------------------------------------------------
def convert_highlighted_text_to_json(highlighted_text: str, key_name="words"):
    """
    Chuyển đổi văn bản có thẻ <span> thành JSON chứa danh sách từ và trạng thái màu của từng từ.
    Giữ dấu cách để giúp frontend hiển thị đúng.
    Đồng thời nhóm các ký tự liên tiếp cùng màu thành một từ duy nhất.

    Args:
        highlighted_text (str): Văn bản có thẻ HTML.
        key_name (str): Tên của key trong JSON (mặc định là "words").

    Returns:
        str: Chuỗi JSON có cấu trúc tối ưu, gọn gàng.
    """
    words = []
    current_index = 0

    # Tách từng phần của câu (bao gồm cả phần highlight và phần không có highlight)
    pattern = re.compile(r'(<span class="highlight-(.*?)">(.*?)</span>)')
    matches = list(pattern.finditer(highlighted_text))

    for match in matches:
        # Lấy phần trước đoạn highlight (bao gồm cả khoảng trắng nếu có)
        before_text = highlighted_text[current_index:match.start()]
        if before_text:
            words.extend([{"text": word, "type": "normal"} for word in re.split(r'(\s+)', before_text) if word])

        # Lấy đoạn bị highlight
        highlight_text = match.group(3)  # Nội dung bên trong <span>
        highlight_type = match.group(2)  # Loại highlight (red, yellow,...)
        words.append({"text": highlight_text, "type": f"highlight-{highlight_type}"})

        # Cập nhật vị trí xử lý tiếp theo
        current_index = match.end()

    # Thêm phần còn lại của câu sau đoạn highlight cuối cùng
    after_text = highlighted_text[current_index:]
    if after_text:
        words.extend([{"text": word, "type": "normal"} for word in re.split(r'(\s+)', after_text) if word])

    # Nhóm các ký tự liên tiếp có cùng màu lại với nhau
    words = group_highlighted_words(words)

    result = {key_name: words}

    return json.dumps(result, ensure_ascii=False, indent=2)

# ----------------------------------------------------------------
def group_highlighted_words(word_list):
    """
    Gộp các ký tự liên tiếp cùng màu thành một cụm từ duy nhất.
    """
    grouped_words = []
    temp_word = ""
    temp_type = ""

    for word in word_list:
        if word["type"] == temp_type:
            temp_word += word["text"]
        else:
            if temp_word:
                grouped_words.append({"text": temp_word, "type": temp_type})
            temp_word = word["text"]
            temp_type = word["type"]

    # Thêm từ cuối cùng vào danh sách
    if temp_word:
        grouped_words.append({"text": temp_word, "type": temp_type})

    return grouped_words

# ----------------------------------------------------------------
def convert_color_style_to_class(html_text: str):
    """
    Chuyển đổi thẻ <span style="color: ...;"> thành <span class="highlight-...">
    
    Args:
        html_text (str): Chuỗi HTML cần chuyển đổi.
    
    Returns:
        str: Chuỗi HTML đã được chuẩn hóa.
    """
    # Định dạng lại các thẻ <span style="color: ...;"> thành <span class="highlight-...">
    html_text = re.sub(r'<span style="color:\s*(green|red|yellow);">', r'<span class="highlight-\1">', html_text)

    return html_text

# ----------------------------------------------------------------
def process_line_1(real_transcripts, is_letter_correct_all_words):
    # Tách các từ và các trạng thái từ is_letter_correct_all_words
    real_transcripts_words = real_transcripts.split(" ")
    letters_correct_status = is_letter_correct_all_words.split(" ")

    # Tạo danh sách chứa HTML cho từng từ
    colored_words = []

    # Lặp qua từng từ
    for word_idx, real_word in enumerate(real_transcripts_words):
        # Nếu vượt quá trạng thái được cung cấp, bỏ qua từ
        if word_idx >= len(letters_correct_status):
            colored_words.append(real_word)
            continue

        # Lấy trạng thái chữ cái của từ hiện tại
        letter_status = letters_correct_status[word_idx]
        word_html = ""

        # Lặp qua từng chữ cái
        for letter_idx, letter in enumerate(real_word):
            if letter_idx < len(letter_status) and letter_status[letter_idx] == "1":
                # Nếu chữ cái đúng, tô màu xanh
                word_html += f'<span style="color: green;">{letter}</span>'
            else:
                # Nếu chữ cái sai, tô màu đỏ
                word_html += f'<span style="color: red;">{letter}</span>'

        # Thêm từ vào danh sách
        colored_words.append(word_html)

    # Ghép danh sách lại thành chuỗi HTML
    return " ".join(colored_words)

# ----------------------------------------------------------------
def process_line_2(real_transcripts_ipa, ipa_transcript):
    """
    So sánh hai chuỗi IPA ký tự theo ký tự và highlight (đánh dấu) các phần sai trên real_transcripts_ipa:
      - Các phần đúng (equal) giữ nguyên.
      - Các phần sai (replace, delete) được bao bọc trong thẻ <span class="highlight-red">...</span>.
      - Các phần chỉ có ở ipa_transcript (insert) không được hiển thị, vì mục tiêu là hiển thị real_transcripts_ipa.
    
    Đầu vào:
      - real_transcripts_ipa: chuỗi IPA của phiên âm gốc.
      - ipa_transcript: chuỗi IPA đã được đối chiếu (có thể có thêm âm tiết/ ký tự thừa).
    
    Trả về:
      - Chuỗi HTML của real_transcripts_ipa với các phần sai được bôi đỏ (bọc trong <span class="highlight-red">...</span>).
    
    Lưu ý: Đảm bảo rằng CSS có định nghĩa cho class "highlight-red", ví dụ:
          .highlight-red { color: red; }
    """
    sm = difflib.SequenceMatcher(None, real_transcripts_ipa, ipa_transcript)
    result = []
    
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            # Đoạn khớp: lấy từ real_transcripts_ipa giữ nguyên
            segment = html.escape(real_transcripts_ipa[i1:i2])
            result.append(segment)
        elif tag in ('replace', 'delete'):
            # Đoạn ở real_transcripts_ipa không khớp (hoặc bị mất so với ipa_transcript): highlight đoạn đó
            segment = html.escape(real_transcripts_ipa[i1:i2])
            result.append(f'<span class="highlight-red">{segment}</span>')
        elif tag == 'insert':
            # Các đoạn chỉ có trong ipa_transcript (insert) không có trong real_transcripts_ipa:
            # Không làm gì, vì ta chỉ hiển thị real_transcripts_ipa.
            continue
    
    return "".join(result)
# ----------------------------------------------------------------
def process_line_2_v3(ipa1, differences, loss):
    import re

    # Tạo mapping từ từ có lỗi thay thế sang danh sách differences của từ đó
    diff_by_word = {}
    for diff in differences:
        word = diff["word"]
        diff_by_word.setdefault(word, []).append(diff)
    
    # Tạo mapping từ từ có lỗi thiếu ký tự (loss) sang danh sách loss của từ đó
    loss_by_word = {}
    for l in loss:
        word = l["correct_word"]
        loss_by_word.setdefault(word, []).append(l)
    
    # Tách ipa1 thành danh sách các từ (giả sử cách nhau bởi khoảng trắng)
    ipa_words = ipa1.split()
    highlighted_words = []
    expected_words = []  # Thêm dòng chứa expected

    # Duyệt qua từng từ trong câu
    for idx, word in enumerate(ipa_words):
        # Lọc differences chỉ cho từ có vị trí trùng với position_word
        pos_to_diff = {d["position"]: d for d in diff_by_word.get(word, []) if d.get("position_word") == idx}
        pos_to_loss = {l["position"]: l for l in loss_by_word.get(word, [])}
        
        highlighted_chars = []
        expected_chars = []
        
        i = 0
        while i < len(word):
            if i in pos_to_loss:
                loss_item = pos_to_loss[i]
                # Chèn ký tự bị thiếu (bôi vàng)
                highlighted_chars.append(
                    f'<span class="highlight-yellow">{loss_item["expected"]}</span>'
                )
                expected_chars.append(f'<span class="expected">{loss_item["expected"]}</span>')

                # Bỏ qua các ký tự gốc tương ứng với loss (tăng index theo độ dài của loss)
                i += len(loss_item["expected"])
                continue
            else:
                if i in pos_to_diff:
                    # Bôi đỏ ký tự sai
                    highlighted_chars.append(
                        f'<span class="highlight-red">{word[i]}</span>'
                    )
                    # Thêm ký tự đúng vào dòng expected
                    expected_chars.append(f'<span class="expected">{pos_to_diff[i]["expected"]}</span>')
                else:
                    # Giữ ký tự gốc (bôi xanh)
                    highlighted_chars.append(
                        f'<span class="highlight-green">{word[i]}</span>'
                    )
                    # Nếu không có lỗi, vẫn giữ ký tự gốc nhưng dưới dạng khoảng trắng để căn chỉnh
                    expected_chars.append(f'<span class="expected">&nbsp;</span>')
                i += 1

        # Nếu có loss ở cuối từ, thêm vào
        if i in pos_to_loss:
            loss_item = pos_to_loss[i]
            highlighted_chars.append(f'<span class="highlight-yellow">{loss_item["expected"]}</span>')
            expected_chars.append(f'<span class="expected">{loss_item["expected"]}</span>')

        highlighted_word = "".join(highlighted_chars)
        expected_word = "".join(expected_chars)

        highlighted_words.append(highlighted_word)
        expected_words.append(expected_word)

    # Sử dụng bảng để căn chỉnh
    result = f"""
    <table style="border-spacing: 0px; font-family: monospace;">
        <tr><td>{' '.join(highlighted_words)}</td></tr>
        <tr><td>{' '.join(expected_words)}</td></tr>
    </table>
    """
    return result
# ----------------------------------------------------------------
def check_diff(re_ipa_matched, real_transcripts_ipa):
    real_words = real_transcripts_ipa.split()
    ipa_words = re_ipa_matched.split()

    differences = []
    error_count = 0

    # So sánh từng cặp từ theo vị trí
    for i, real_word in enumerate(real_words):
        temp_real_word = re.sub(r"[.,?!…]ˈ", "",real_word)
        # Nếu ipa có ít từ hơn real, tránh lỗi IndexError
        temp_ipa_word = re.sub(r"[.,?!…]ˈ", "",ipa_words[i]) if i < len(ipa_words) else ""
        
        # Lấy độ dài so sánh là max của 2 từ
        max_len = max(len(temp_ipa_word), len(temp_real_word))
        for j in range(max_len):
            if j >= len(temp_real_word):
                break
            # Nếu chỉ số vượt quá độ dài của từ, sử dụng ký tự cuối cùng làm so sánh
            expected = temp_ipa_word[j] if j < len(temp_ipa_word) else (temp_ipa_word[-1] if temp_ipa_word else None)
            actual = temp_real_word[j]
            if expected != actual:
                differences.append({
                    "word": real_word,      # từ có lỗi trong real_transcripts_ipa
                    "position": j,         # vị trí ký tự so sánh
                    "expected": expected,  # ký tự đúng theo ipa_words
                    "actual": actual,      # ký tự sai trong real_transcripts_ipa
                    "wrong_word": ipa_words[i],
                    "position_word": i  # vị trí trong câu
                })
                error_count += 1

    return differences, error_count
# ----------------------------------------------------------------

def process_line_3_v3(real_transcripts_ipa, matched_transcripts_ipa, ipa_transcript):
    real_words = real_transcripts_ipa.split()
    ipa_words = matched_transcripts_ipa.split()

    differences = []
    error_count = 0

    # So sánh từng cặp từ theo vị trí
    for i, ipa_word in enumerate(ipa_words):
        temp_ipa_word = ipa_word.replace("ˈ", "")
        # Nếu real có ít từ hơn ipa, tránh lỗi IndexError
        real_word = real_words[i].replace("ˈ", "") if i < len(real_words) else ""
        
        # Lấy độ dài so sánh là max của 2 từ
        max_len = max(len(real_word), len(temp_ipa_word))
        for j in range(max_len):
            if j >= len(temp_ipa_word):
                break
            # Nếu chỉ số vượt quá độ dài của từ, sử dụng ký tự cuối cùng làm so sánh
            expected = real_word[j] if j < len(real_word) else (real_word[-1] if real_word else None)
            actual = temp_ipa_word[j]
            if expected != actual:
                for k, elemnent in enumerate(ipa_transcript.replace("ˈ", "").split()):
                    if elemnent == ipa_word:
                        differences.append({
                            "word": ipa_word,      # từ có lỗi trong ipa_transcript
                            "position": j,         # vị trí ký tự so sánh
                            "expected": expected,  # ký tự đúng theo real_transcripts_ipa
                            "actual": actual,       # ký tự sai trong ipa_transcripts_ipa
                            "position_word": k # vị trí ipa trong câu
                        })
                        error_count += 1

    return differences, error_count

# ----------------------------------------------------------------
def process_line_4_v1(ipa1, differences, loss):
    """
    ipa1: chuỗi IPA hoàn chỉnh (ví dụ: "tʃɪkən kʊkɪŋ")
    differences: danh sách dict cho lỗi thay thế ký tự, mỗi dict có cấu trúc:
        {
            "word": ipa_word,      # từ có lỗi (thay thế ký tự)
            "position": j,         # vị trí ký tự lỗi trong từ
            "expected": ...,       # ký tự đúng
            "actual": ...,         # ký tự sai
            "position_word": i     # vị trí của từ trong câu (ipa_words)
        }
    loss: danh sách dict cho các ký tự bị thiếu, mỗi dict có cấu trúc:
        {
            "word": ipa_word,      # từ bị thiếu ký tự
            "position": j,         # vị trí ký tự bị thiếu trong từ
            "expected": ...        # ký tự mà từ này còn thiếu
        }
    
    Hàm trả lại chuỗi ipa1 được bôi màu:
      - Với từ có lỗi thay thế (trong differences) → ký tự sai (actual) được bôi đỏ,
        *nhưng chỉ áp dụng cho từ có vị trí trùng với giá trị position_word trong differences*.
      - Với từ bị thiếu ký tự (trong loss) → chèn ký tự đúng (expected) được bôi vàng.
      - Các ký tự không lỗi được bôi xanh.
      
    Lưu ý: Nếu tại cùng một vị trí có cả loss và differences,
      thì ưu tiên hiển thị loss và không hiển thị ký tự gốc (và diff) tại vị trí đó.
    """
    # Tạo mapping từ từ có lỗi thay thế sang danh sách differences của từ đó
    diff_by_word = {}
    for diff in differences:
        word = diff["word"]
        diff_by_word.setdefault(word, []).append(diff)
    
    # Tạo mapping từ từ có lỗi thiếu ký tự (loss) sang danh sách loss của từ đó
    loss_by_word = {}
    for l in loss:
        word = l["word"]
        loss_by_word.setdefault(word, []).append(l)
    
    # Tách ipa1 thành danh sách các từ (giả sử cách nhau bởi khoảng trắng)
    ipa_words = ipa1.split()
    highlighted_words = []
    
    # Sử dụng enumerate để biết vị trí của từ trong câu
    for idx, word in enumerate(ipa_words):
        # Lọc differences chỉ cho từ có vị trí trùng với position_word
        pos_to_diff = {d["position"]: d for d in diff_by_word.get(word, []) if d.get("position_word") == idx}
        pos_to_loss = {l["position"]: l for l in loss_by_word.get(word, [])}
        
        highlighted_chars = []
        # Duyệt qua các vị trí từ 0 đến len(word)+1 để bắt cả chỗ chèn sau cùng
        for i in range(len(word) + 1):
            if i in pos_to_loss:
                # Nếu có loss tại vị trí i, chèn ký tự bị thiếu (bôi vàng)
                highlighted_chars.append(
                    f'<span class="highlight-yellow">{pos_to_loss[i]["expected"]}</span>'
                )
                # Nếu cùng vị trí có diff thì chỉ hiển thị loss (không hiển thị ký tự gốc)
                if i in pos_to_diff:
                    continue
                # Nếu không có diff và vị trí i thuộc trong từ, hiển thị ký tự gốc
                if i < len(word):
                    highlighted_chars.append(
                        f'<span class="highlight-green">{word[i]}</span>'
                    )
            else:
                # Nếu không có loss tại vị trí i, xử lý ký tự gốc (với diff nếu có)
                if i < len(word):
                    if i in pos_to_diff:
                        highlighted_chars.append(
                            f'<span class="highlight-red">{pos_to_diff[i]["actual"]}</span>'
                        )
                    else:
                        highlighted_chars.append(
                            f'<span class="highlight-green">{word[i]}</span>'
                        )
        highlighted_word = "".join(highlighted_chars)
        highlighted_words.append(highlighted_word)
    
    result = " ".join(highlighted_words)
    return result

# ----------------------------------------------------------------

def reinsert_dashes(original, matched):
    """
    original: chuỗi gốc có dấu trừ, ví dụ "Not - on my friends last -"
    matched: chuỗi matched không chứa dấu trừ, ví dụ "nɑt  ɔn maɪ frɛndz læst"
    
    Hàm này sẽ trả về chuỗi matched sau khi chèn lại dấu trừ ở vị trí tương ứng,
    kết quả: "nɑt - ɔn maɪ frɛndz læst -"
    """
    # Tách original thành các token, giữ lại dấu '-' làm token riêng biệt
    original_tokens = re.findall(r"[^\s-]+|[-]", original)
    # Tách matched thành các token, chỉ lấy các token không phải dấu trừ
    matched_tokens = re.findall(r"[^\s-]+", matched)
    
    result_tokens = []
    matched_index = 0

    for token in original_tokens:
        if token == "-":
            # Nếu token của original là dấu '-', thêm dấu '-' vào kết quả
            result_tokens.append("-")
        else:
            # Nếu không phải dấu '-', lấy token từ matched_tokens nếu còn
            if matched_index < len(matched_tokens):
                result_tokens.append(matched_tokens[matched_index])
                matched_index += 1
            else:
                # Nếu hết token trong matched, bạn có thể quyết định xử lý riêng (ở đây ta thêm chuỗi rỗng)
                result_tokens.append("")
                
    # Ghép các token lại thành chuỗi, các token cách nhau bởi khoảng trắng
    return " ".join(result_tokens)

# ----------------------------------------------------------------
def find_missing_letters(correct_word, matched_word):
    """
    So sánh correct_word với matched_word để tìm phần ký tự bị thiếu (loss).
    Nhưng trước tiên, kiểm tra xem matched_word có phải là subsequence của correct_word hay không.
    Nếu không phải, tức có ký tự không khớp về thứ tự, thì bỏ qua (trả về [] cho từ đó).
    Nếu đúng, thì tiến hành so sánh chi tiết và ghi nhận loss.
    """
    # Bước 1: Kiểm tra subsequence
    j = 0
    for i in range(len(correct_word)):
        if j < len(matched_word) and correct_word[i] == matched_word[j]:
            j += 1
    if j != len(matched_word):
        # matched_word không phải là subsequence của correct_word, bỏ qua từ này.
        return []
    
    # Bước 2: So sánh chi tiết (chỉ khi matched_word là subsequence)
    i, j = 0, 0
    differences = []
    missing_chars = ""
    missing_start = None

    while i < len(correct_word) and j < len(matched_word):
        if correct_word[i] == matched_word[j]:
            if missing_chars:
                differences.append({
                    "word": matched_word,
                    "correct_word": correct_word,
                    "position": missing_start,
                    "expected": missing_chars
                })
                missing_chars = ""
                missing_start = None
            i += 1
            j += 1
        else:
            if missing_start is None:
                missing_start = i
            missing_chars += correct_word[i]
            i += 1

    if i < len(correct_word):
        missing_chars += correct_word[i:]
        differences.append({
            "word": matched_word,
            "correct_word": correct_word,
            "position": missing_start if missing_start is not None else len(matched_word),
            "expected": missing_chars
        })

    return differences


def compare_ipa(ipa1, ipa2):
    """
    ipa1: chuỗi IPA đầy đủ (ví dụ: "tɑmz rɪkˈwɛst ɪz ənˈriznəbəl.")
    ipa2: chuỗi IPA ghi nhận (ví dụ: "tərmz rɪkˈwɛst ɪz ˈrizənəbəl.")
    
    Tách các chuỗi thành từng từ và so sánh theo thứ tự.
    Trả về danh sách loss chứa các lỗi thiếu ký tự.
    """
    ipa1_words = ipa1.split()
    ipa2_words = ipa2.split()
    
    loss = []
    for word1, word2 in zip(ipa1_words, ipa2_words):
        diff = find_missing_letters(word1, word2)
        if diff:
            loss.extend(diff)
    return loss


# ----------------------------------------------------------------

def reinsert_missing_ipa(matched_transcripts_ipa, loss):
    """
    matched_transcripts_ipa: chuỗi IPA ghi nhận (ví dụ: "tərmz rɪkˈwɛst ɪz ˈrizənəbəl.")
    loss: danh sách dict cho các ký tự bị thiếu, mỗi dict có cấu trúc:
          {
              "word": ipa_word,       # từ bị thiếu ký tự (trong ipa2)
              "position": j,          # vị trí ký tự bị thiếu trong từ
              "expected": ...         # chuỗi ký tự còn thiếu cần chèn vào
          }
    Hàm trả về một chuỗi mới, trong đó với mỗi từ của matched_transcripts_ipa,
    nếu có loss tương ứng thì chèn các ký tự còn thiếu vào vị trí được chỉ định.
    """
    # Tách ipa2 thành danh sách các từ (giả sử cách nhau bởi khoảng trắng)
    words = matched_transcripts_ipa.split()
    
    # Vì loss được thu thập theo thứ tự so sánh từng cặp từ, ta giả sử rằng
    # thứ tự các loss trong danh sách trùng với thứ tự xuất hiện các từ trong ipa2.
    new_words = []
    loss_index = 0  # dùng để duyệt qua loss

    for word in words:
        # Tập hợp các loss tương ứng với từ hiện tại (nếu có)
        corrections = []
        # Nếu từ hiện tại khớp với loss["word"], ta thu thập hết các mục loss của từ đó.
        while loss_index < len(loss) and loss[loss_index]["word"] == word:
            corrections.append(loss[loss_index])
            loss_index += 1
        
        # Sắp xếp corrections theo vị trí tăng dần (nếu có nhiều chỗ chèn)
        corrections.sort(key=lambda x: x["position"])
        
        # Chèn các ký tự bị thiếu vào từ
        new_word = word
        offset = 0  # offset tăng khi ta chèn thêm ký tự
        for corr in corrections:
            pos = corr["position"] + offset
            # Chèn chuỗi ký tự cần bổ sung vào new_word tại vị trí pos
            new_word = new_word[:pos] + corr["expected"] + new_word[pos:]
            offset += len(corr["expected"])
        
        new_words.append(new_word)
    
    # Ghép lại thành chuỗi hoàn chỉnh, các từ cách nhau bởi khoảng trắng
    return " ".join(new_words)


# # Ví dụ sử dụng:
# matched_transcripts_ipa = "tərmz rɪkˈwɛst ɪz ˈrizənəbəl."
# # Giả sử hàm so sánh đã tạo ra loss như sau:
# loss = [
#     {'word': 'ˈrizənəbəl.', 'position': 0, 'expected': 'ən'},
#     # Nếu có nhiều loss cho cùng từ, chúng sẽ được xử lý theo thứ tự
#     # ví dụ: {'word': 'ˈrizənəbəl.', 'position': 6, 'expected': 'n'}
# ]

# result = reinsert_missing_ipa(matched_transcripts_ipa, loss)
# print("Result IPA:", result)