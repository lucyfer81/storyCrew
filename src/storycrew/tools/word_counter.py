"""中文字数统计工具

提供准确的中文语境下的字数统计功能：
- 汉字（CJK统一汉字）
- 英文单词（连续字母序列）
- 数字序列（连续数字）
- 排除：空格、标点符号、换行符等

作者：StoryCrew Team
日期：2026-01-16
目的：解决 len(text) 计算字符数与中文字数概念偏差的问题
"""
import re
from typing import Dict


def count_chinese_words(text: str) -> int:
    """统计中文字数（汉字+英文单词，排除空白和标点）

    统计规则：
    - 汉字（CJK统一汉字）：每个算1个字
    - 英文单词：连续的字母序列算1个词
    - 数字：连续数字序列算1个词
    - 排除：空格、标点符号、换行符等

    Args:
        text: 待统计的文本

    Returns:
        int: 字数（汉字+英文单词数）

    Examples:
        >>> count_chinese_words("你好，世界！")
        4
        >>> count_chinese_words("Hello world 你好")
        4  # Hello(1) + world(1) + 你好(2)
        >>> count_chinese_words("第1章：开始")
        4  # 第(1) + 1(1) + 章(1) + 开始(2)
        >>> count_chinese_words("林晓雨以为继承祖母的咖啡馆是理所当然的事")
        19
    """
    if not text:
        return 0

    # 统计英文单词（在移除标点之前，保持空格分隔）
    english_words = len(re.findall(r'[a-zA-Z]+', text))

    # 统计数字序列
    numbers = len(re.findall(r'\d+', text))

    # 移除标点符号和空白后统计汉字
    # 移除所有空白字符（包括空格、制表符、换行符等）
    text_clean = re.sub(r'\s+', '', text)

    # 移除常见标点符号
    # 中文标点范围
    text_clean = re.sub(r'[\u3000-\u303F\uFF00-\uFFEF]', '', text_clean)
    # 英文标点
    text_clean = re.sub(r'[!"#$%&\'()*+,\-./:;<=>?@[\\\]^_`{|}~]', '', text_clean)

    # 统计汉字（CJK统一汉字范围）
    chinese_chars = len(re.findall(r'[\u4E00-\u9FFF]', text_clean))

    return chinese_chars + english_words + numbers


def analyze_text_statistics(text: str) -> Dict[str, int]:
    """分析文本的详细统计信息

    Args:
        text: 待分析的文本

    Returns:
        Dict包含：
        - chinese_chars: 汉字数
        - english_words: 英文单词数
        - numbers: 数字序列数
        - total_words: 总字数（汉字+英文单词+数字）
        - char_count: 总字符数（含标点空白）
        - char_count_no_spaces: 总字符数（不含空白）
    """
    if not text:
        return {
            'chinese_chars': 0,
            'english_words': 0,
            'numbers': 0,
            'total_words': 0,
            'char_count': 0,
            'char_count_no_spaces': 0
        }

    # 移除空白后的文本（用于统计）
    text_no_spaces = re.sub(r'\s+', '', text)

    # 统计汉字
    chinese_chars = len(re.findall(r'[\u4E00-\u9FFF]', text_no_spaces))

    # 统计英文单词
    english_words = len(re.findall(r'[a-zA-Z]+', text))

    # 统计数字序列
    numbers = len(re.findall(r'\d+', text))

    return {
        'chinese_chars': chinese_chars,
        'english_words': english_words,
        'numbers': numbers,
        'total_words': chinese_chars + english_words + numbers,
        'char_count': len(text),
        'char_count_no_spaces': len(text_no_spaces)
    }


# 测试用例（当直接运行此文件时执行）
if __name__ == "__main__":
    test_cases = [
        ("你好世界", 4),
        ("Hello, world!", 2),
        ("第1章：开始", 5),  # 第(1) + 1(1) + 章(1) + 开始(2) = 5
        ("林晓雨以为继承祖母的咖啡馆是理所当然的事", 20),  # 20个汉字
        ("", 0),
        ("你好，世界！", 4),  # 测试标点排除
        ("Hello world 你好", 4),  # 测试中英混合
    ]

    print("=" * 60)
    print("字数统计测试")
    print("=" * 60)

    all_passed = True
    for text, expected in test_cases:
        result = count_chinese_words(text)
        passed = result == expected
        status = "✅" if passed else f"❌ (预期{expected}，得到{result})"
        print(f"{status} '{text}' -> {result}字")

        if not passed:
            all_passed = False

    print("=" * 60)
    print(f"测试结果: {'全部通过 ✅' if all_passed else '存在失败 ❌'}")
    print()

    # 详细统计示例
    print("=" * 60)
    print("详细统计示例")
    print("=" * 60)

    sample_text = """
    第1章：破碎的继承

    林晓雨以为继承祖母的咖啡馆是理所当然的事，直到她发现那份改变一切的遗嘱——一个月内结婚，否则咖啡馆将被捐赠给慈善机构。
    """

    stats = analyze_text_statistics(sample_text)
    print(f"示例文本：{sample_text.strip()}")
    print()
    print(f"汉字数：{stats['chinese_chars']}")
    print(f"英文单词数：{stats['english_words']}")
    print(f"数字序列数：{stats['numbers']}")
    print(f"总字数（汉字+英文+数字）：{stats['total_words']}")
    print(f"总字符数（含空白）：{stats['char_count']}")
    print(f"总字符数（不含空白）：{stats['char_count_no_spaces']}")
