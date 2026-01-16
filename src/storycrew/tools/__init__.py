"""StoryCrew Tools Package

提供文本处理、字数统计等工具函数。
"""

from .word_counter import count_chinese_words, analyze_text_statistics

__all__ = ['count_chinese_words', 'analyze_text_statistics']
