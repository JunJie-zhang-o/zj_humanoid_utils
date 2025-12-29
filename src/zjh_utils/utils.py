



def zprint(text, border_char="="):
    """
    用指定边框字符包围文本并打印
    
    Args:
        text (str): 要打印的文本
        border_char (str): 边框字符，默认为"="，也可以使用"-"
    """
    if not text:
        return
    
    # 计算边框长度（中文字符按2个字符计算）
    border_length = 0
    for char in text:
        if ord(char) > 127:  # 非ASCII字符（如中文）
            border_length += 2
        else:
            border_length += 1
    
    border = border_char * (border_length + 4)  # 左右各加2个边框字符
    print(border)
    print(f"{border_char} {text} {border_char}")
    print(border)