import csv
import os
import sys
import ctypes

from openai import OpenAI

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(SCRIPT_DIR, "translate.csv")
KEY_FILE = os.path.join(SCRIPT_DIR, "API_key.key")

# 中文语言名 → 英文语言名映射（不在映射中的直接用中文名）
LANG_MAP = {
    "英文": "English",
    "中文": "Chinese",
    "日语": "Japanese",
    "日文": "Japanese",
    "韩语": "Korean",
    "韩文": "Korean",
    "法语": "French",
    "法文": "French",
    "德语": "German",
    "德文": "German",
    "西班牙语": "Spanish",
    "西班牙文": "Spanish",
    "俄语": "Russian",
    "俄文": "Russian",
    "意大利语": "Italian",
    "意大利文": "Italian",
    "葡萄牙语": "Portuguese",
    "葡萄牙文": "Portuguese",
    "阿拉伯语": "Arabic",
    "阿拉伯文": "Arabic",
    "泰语": "Thai",
    "泰文": "Thai",
    "越南语": "Vietnamese",
    "越南文": "Vietnamese",
    "世界语": "Esperanto",
}


def msgbox(title, text, icon=0):
    """Windows 原生弹窗。icon: 0=信息, 16=错误"""
    ctypes.windll.user32.MessageBoxW(0, text, title, icon)


def load_api_key():
    """从 API_key.key 文件读取密钥，若不存在或为空则提示用户输入"""
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            key = f.read().strip()
        if key:
            return key

    msg = "请输入deepseek 的 Api Key"
    print(msg)
    msgbox("API Key", msg)
    key = input().strip()
    if key:
        with open(KEY_FILE, "w", encoding="utf-8") as f:
            f.write(key)
    return key


def main():
    # 1. 读取 CSV
    if not os.path.exists(CSV_FILE):
        msg = f"文件不存在：{CSV_FILE}"
        print(msg)
        msgbox("翻译失败", msg, 16)
        input("按回车键退出...")
        sys.exit(1)

    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 2:
        msg = "CSV 文件为空或缺少数据行"
        print(msg)
        msgbox("翻译失败", msg, 16)
        input("按回车键退出...")
        sys.exit(1)

    header = rows[0]

    # 2. 找出中文文本列和所有【翻译】列
    source_col = None
    for i, h in enumerate(header):
        if "中文" in h and "文本" in h and "【翻译】" not in h:
            source_col = i
            break

    if source_col is None:
        msg = "未找到中文文本列（列名需包含\"中文\"和\"文本\"，且不含【翻译】标记）"
        print(msg)
        msgbox("翻译失败", msg, 16)
        input("按回车键退出...")
        sys.exit(1)

    # 找出所有需要翻译的目标列：列名包含【翻译】
    target_cols = []  # [(col_index, lang_cn, lang_en)]
    for i, h in enumerate(header):
        if "【翻译】" in h:
            # 提取语言名：【翻译】前面的部分，去掉"文本"后缀
            lang_cn = h.replace("【翻译】", "").strip()
            if lang_cn.endswith("文本"):
                lang_cn = lang_cn[:-2]
            target_cols.append((i, lang_cn))

    if not target_cols:
        msg = "未找到需要翻译的列（列名需包含【翻译】标记，如\"英文文本【翻译】\"）"
        print(msg)
        msgbox("翻译失败", msg, 16)
        input("按回车键退出...")
        sys.exit(1)

    # 补全列数不足的行
    max_cols = len(header)
    for row in rows:
        while len(row) < max_cols:
            row.append("")

    # 3. 收集所有待翻译的条目
    pending = []  # [(row_idx, col_idx, chinese_text, lang_cn, lang_en)]
    for row_idx in range(1, len(rows)):
        chinese_text = rows[row_idx][source_col].strip()
        if not chinese_text:
            continue
        for col_idx, lang_cn in target_cols:
            current = rows[row_idx][col_idx].strip() if col_idx < len(rows[row_idx]) else ""
            if current == "":
                pending.append((row_idx, col_idx, chinese_text, lang_cn))

    if not pending:
        msg = "所有条目已翻译，无需操作"
        print(msg)
        msgbox("翻译完成", msg)
        input("按回车键退出...")
        return

    # 4. 构建批量翻译 prompt
    lines = []
    for idx, (row_idx, col_idx, chinese, lang_cn) in enumerate(pending):
        lang_en = LANG_MAP.get(lang_cn, lang_cn)
        lines.append(f"{idx + 1}. 目标语言: {lang_en}({lang_cn}) | 原文: {chinese}")
    terms_text = "\n".join(lines)

    api_key = load_api_key()
    if not api_key:
        msg = "API Key 未提供，无法继续翻译"
        print(msg)
        msgbox("翻译失败", msg, 16)
        input("按回车键退出...")
        sys.exit(1)

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )

    system_prompt = (
        "你是一个专业的电气自动化领域翻译专家。"
        "我会给你若干条待翻译的内容，每条格式为：序号. 目标语言: 语言名 | 原文: 中文术语。"
        "请将每条原文翻译成对应的目标语言，每个翻译结果独占一行，格式为：序号. 翻译结果。"
        "不要输出任何解释，只输出翻译结果。"
    )

    print(f"待翻译 {len(pending)} 条：")
    for idx, (row_idx, col_idx, chinese, lang_cn) in enumerate(pending):
        print(f"  #{idx + 1} [{lang_cn}] {chinese}")
    print("-" * 40)

    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": terms_text},
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )

        result_text = response.choices[0].message.content.strip()
        print(f"API 返回：\n{result_text}")
        print("-" * 40)

        # 5. 解析返回结果
        translations = []
        for line in result_text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            for sep in (". ", ".", " "):
                idx_sep = line.find(sep)
                if idx_sep > 0 and line[:idx_sep].isdigit():
                    line = line[idx_sep + len(sep):].strip()
                    break
            line = line.strip("*\"'")
            translations.append(line)

        if len(translations) != len(pending):
            print(f"警告：翻译结果数量({len(translations)})与待翻译数量({len(pending)})不匹配")

        # 6. 写回 CSV
        for idx, (row_idx, col_idx, chinese, lang_cn) in enumerate(pending):
            if idx < len(translations):
                rows[row_idx][col_idx] = translations[idx]

        with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

        # 7. 打印结果
        print("翻译结果：")
        for idx, (row_idx, col_idx, chinese, lang_cn) in enumerate(pending):
            eng = translations[idx] if idx < len(translations) else "无结果"
            print(f"  [{lang_cn}] {chinese} → {eng}")

        msg = f"翻译完成！共翻译 {len(pending)} 条"
        print(f"\n{msg}")
        msgbox("翻译完成", msg)

    except Exception as e:
        msg = f"翻译出错：{e}"
        print(msg)
        msgbox("翻译失败", msg, 16)

    input("按回车键退出...")


if __name__ == "__main__":
    main()
