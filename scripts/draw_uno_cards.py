from PIL import Image, ImageDraw, ImageFont
import math
import os

def draw_special_symbol(draw, x, y, symbol_type, size, fill_color):
    """绘制特殊符号: Skip, Reverse"""
    if symbol_type == "Skip":
        # 禁止符号 (圆圈 + 斜杠)
        r = size / 2
        line_width = max(int(size * 0.1), 3)
        # 圆圈
        draw.ellipse([x-r, y-r, x+r, y+r], outline=fill_color, width=line_width)
        # 斜杠 (左上到右下)
        offset = r * 0.7
        draw.line([x-offset, y-offset, x+offset, y+offset], fill=fill_color, width=line_width)
    
def draw_arrow_symbol(draw, x, y, size, fill_color):
    """专门绘制反转箭头，不带旋转"""
    offset_y = size * 0.12  # 进一步减小上下间距
    arrow_w = size * 0.95   # 增加总宽度
    arrow_h = size * 0.40   # 箭头头部高度
    head_len = size * 0.35  # 箭头头部长度
    
    # 箭柄尺寸
    bar_h = arrow_h * 0.40  # 杆的粗细
    bar_w = arrow_w - head_len * 0.2 # 杆的总长 (让杆稍微插入头部一点)
    
    # 我们让两个箭头的杆在水平方向上是对齐的 (即占据相同的 x 范围)
    # 假设杆的中心在 x
    # 杆的范围: [x - bar_w/2, x + bar_w/2]
    
    def draw_single_arrow(ax, ay, direction="right"):
        # 杆的半高
        half_bar_h = bar_h / 2
        
        # 杆的左右坐标 (居中)
        bar_left = ax - bar_w / 2
        bar_right = ax + bar_w / 2
        
        draw.rectangle([bar_left, ay - half_bar_h, bar_right, ay + half_bar_h], fill=fill_color)
        
        if direction == "right":
            # 箭头在右边，尖端位于 bar_right 稍微偏右的位置? 或者就把 bar_right 当做箭头底座位置
            # 为了美观，箭头尖端通常在 bar_right + head_len 处? 
            # 或者是：箭头覆盖在杆的末端。
            # 让箭头尖端位于 bar_right + head_len * 0.2
            # 箭头底座位于 bar_right - head_len * 0.8
            
            tip_x = bar_right + head_len * 0.2 + size * 0.12
            base_x = tip_x - head_len
            
            poly = [
                (base_x, ay - arrow_h/2),
                (tip_x, ay),
                (base_x, ay + arrow_h/2)
            ]
            draw.polygon(poly, fill=fill_color)
            
        else: # left
            # 箭头在左边
            tip_x = bar_left - head_len * 0.2 - size * 0.12
            base_x = tip_x + head_len
            
            poly = [
                (base_x, ay - arrow_h/2),
                (tip_x, ay),
                (base_x, ay + arrow_h/2)
            ]
            draw.polygon(poly, fill=fill_color)

    shift_x = size * 0.12
    # 上箭头向右 (向右移动)
    draw_single_arrow(x + shift_x, y - offset_y, "right")
    # 下箭头向左 (向左移动)
    draw_single_arrow(x - shift_x, y + offset_y, "left")

def paste_rotated_layer(target_img, x, y, symbol_func, size, color, angle):
    """创建一个临时层绘制符号并旋转，然后粘贴到目标图像"""
    # 画布大小要足够容纳旋转后的图形
    canvas_size = int(size * 1.5)
    layer = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    
    # 在中心绘制
    symbol_func(d, canvas_size//2, canvas_size//2, size, color)
    
    # 旋转
    rotated_layer = layer.rotate(angle, resample=Image.BICUBIC)
    
    # 计算粘贴位置 (中心对齐)
    paste_x = int(x - canvas_size//2)
    paste_y = int(y - canvas_size//2)
    
    target_img.paste(rotated_layer, (paste_x, paste_y), rotated_layer)

def draw_colored_ellipse_symbol(draw, x, y, size, _ignored_color):
    """绘制四色椭圆(用于角落)，不需要 mask，直接画扇形"""
    # 比例与中心大椭圆一致 (1.2:1)
    # size 是宽 (长轴)
    w = size
    h = size / 1.2
    
    # 边界框
    bbox = [x - w/2, y - h/2, x + w/2, y + h/2]
    
    # 定义四色 (硬编码或传参)
    colors = {
        "red": (255, 85, 85),
        "blue": (85, 85, 255),
        "green": (85, 170, 85),
        "yellow": (255, 170, 0)
    }
    
    # 绘制四个扇形
    # PIL 坐标系：0度在右边，顺时针增加
    # 右下 (绿): 0-90
    draw.pieslice(bbox, 0, 90, fill=colors["green"])
    # 左下 (黄): 90-180
    draw.pieslice(bbox, 90, 180, fill=colors["yellow"])
    # 左上 (红): 180-270
    draw.pieslice(bbox, 180, 270, fill=colors["red"])
    # 右上 (蓝): 270-360
    draw.pieslice(bbox, 270, 360, fill=colors["blue"])

def create_uno_card(color, value, output_path="uno_card.png"):
    # 卡牌尺寸与比例 (约 2:3)
    width, height = 400, 600
    border_radius = 40
    
    # 创建画布 (RGBA 支持透明度)
    card = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(card)

    # 1. 绘制卡牌背景 (圆角矩形)
    # 颜色映射
    colors = {
        "red": (255, 85, 85),
        "blue": (85, 85, 255),
        "green": (85, 170, 85),
        "yellow": (255, 170, 0),
        "black": (42, 42, 42),
        "light_brown": (181, 101, 29) # 浅棕色
    }
    bg_color = colors.get(color.lower(), colors["red"])

    # Calculate tinted white (opaque)
    # 混合白色和背景色，模拟半透明效果
    # 85% 白色 + 15% 背景色
    tr = int(bg_color[0] * 0.15 + 255 * 0.85)
    tg = int(bg_color[1] * 0.15 + 255 * 0.85)
    tb = int(bg_color[2] * 0.15 + 255 * 0.85)
    tinted_white = (tr, tg, tb, 255)
    
    draw.rounded_rectangle([10, 10, width-10, height-10], radius=border_radius, fill=bg_color, outline="white", width=8)

    # 2. 绘制中间的椭圆 (倾斜效果)
    # 创建一个临时层来旋转椭圆
    ellipse_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    e_draw = ImageDraw.Draw(ellipse_layer)
    
    ellipse_box = [20, 150, width-20, height-150]
    
    if value == "+4" or value == "Wild":
        # +4 和 Wild 牌特殊处理：四色椭圆
        # 我们先画一个白底椭圆作为蒙版或者底
        # 更简单的做法：直接在椭圆区域内画四个扇形或者矩形，然后用椭圆去切它。 
        
        # 1. 创建一个足够大的正方形画布来画四色，然后缩放到椭圆大小？不，直接在椭圆层画。
        # 椭圆中心
        cx, cy = width // 2, height // 2
        
        # 绘制整个白色完全不透明椭圆底 (改为不透明)
        e_draw.ellipse(ellipse_box, fill=(255, 255, 255, 255))
        
        # 使用 mask 方式来限制四色只显示在椭圆内
        # 创建一个纯椭圆 mask
        mask = Image.new("L", (width, height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse(ellipse_box, fill=255)
        
        # 创建一个四色层
        color_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        c_draw = ImageDraw.Draw(color_layer)
        
        # 定义四色
        # 左上: 红, 右上: 蓝, 左下: 黄, 右下: 绿 (或者按 UNO Logo 顺序)
        # 这里按题目要求: 红蓝黄绿
        # 简单的四格切分
        
        e_w, e_h = width, height
        # 左上 - 红
        c_draw.rectangle([0, 0, cx, cy], fill=colors["red"])
        # 右上 - 蓝 (注意 UNO 配色里蓝色通常在右边或下边)
        c_draw.rectangle([cx, 0, e_w, cy], fill=colors["blue"])
        # 左下 - 黄
        c_draw.rectangle([0, cy, cx, e_h], fill=colors["yellow"])
        # 右下 - 绿
        c_draw.rectangle([cx, cy, e_w, e_h], fill=colors["green"])
        
        # 将四色层应用椭圆 mask
        # 复合：先将 color_layer update 到 ellipse_layer 上，但只在 mask 区域
        # 实际上我们已经画了半透明白底。如果直接覆盖四色，也是可以的。
        # 我们把 color_layer 作为一个新的图像，应用 mask
        
        color_circle = Image.composite(color_layer, Image.new("RGBA", (width, height), (0,0,0,0)), mask)
        
        # 把裁切好的四色椭圆贴到 ellipse_layer 上 (或者直接以此替代 ellipse_layer)
        # 考虑到如果需要半透明，可以在 composite 前调节 color_layer alpha
        # 这里直接替换
        ellipse_layer = color_circle 
    
    elif value == "Back":
        # 牌背：中间的椭圆为大红色 (255, 0, 0)
        e_draw.ellipse(ellipse_box, fill=(255, 0, 0))

    elif value == "Default":
        # Default 卡牌：使用不透明的淡色椭圆
        e_draw.ellipse(ellipse_box, fill=tinted_white)

    elif value == "PLAYER":
        # 角色牌：使用不透明的淡色椭圆
        e_draw.ellipse(ellipse_box, fill=tinted_white)

    else:
        # 普通牌：使用不透明的淡色椭圆
        e_draw.ellipse(ellipse_box, fill=tinted_white)

    ellipse_layer = ellipse_layer.rotate(25, resample=Image.BICUBIC)
    card.paste(ellipse_layer, (0, 0), ellipse_layer)

    # 3. 字体设置
    try:
        # 尝试使用系统字体 DejaVuSans-Bold (常见于 Linux)
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font_large = ImageFont.truetype(font_path, 250)
        font_medium = ImageFont.truetype(font_path, 180) # 用于 +2
        font_medium_sym = ImageFont.truetype(font_path, 150) # 用于 back 中心
        font_small = ImageFont.truetype(font_path, 80)
        font_small_sym = ImageFont.truetype(font_path, 60) # 用于角落 +2
        font_label = ImageFont.truetype(font_path, 50)
    except OSError:
        try:
           # 备用尝试 Arial
            font_large = ImageFont.truetype("arialbd.ttf", 250)
            font_medium = ImageFont.truetype("arialbd.ttf", 180)
            font_medium_sym = ImageFont.truetype("arialbd.ttf", 150)
            font_small = ImageFont.truetype("arialbd.ttf", 80)
            font_small_sym = ImageFont.truetype("arialbd.ttf", 60)
            font_label = ImageFont.truetype("arialbd.ttf", 50)
        except OSError:
            # 最后兜底
            print("警告: 未找到指定字体，使用默认字体 (可能较小)")
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_medium_sym = ImageFont.load_default()
            font_small = ImageFont.load_default()
            font_small_sym = ImageFont.load_default()
            font_label = ImageFont.load_default()

    # 4. 绘制中心和角落内容
    
    # 统一处理中心绘制逻辑
    if value == "+2" or value == "+4":
        # 中心绘制 +n
        draw.text((width//2, height//2), value, fill="white", font=font_medium, anchor="mm", stroke_width=5, stroke_fill="black")
        
        # 角落绘制 +n
        draw.text((70, 60), value, fill="white", font=font_small_sym, anchor="mm")
        draw.text((width-70, height-60), value, fill="white", font=font_small_sym, anchor="mm")
        
        # 右上角 UNO
        draw.text((width-85, 60), "UNO", fill="white", font=font_label, anchor="mm")
        # 左下角 ONO
        draw.text((85, height-60), "THU", fill="white", font=font_label, anchor="mm")

    elif value == "Back":
        # 牌背：中间显示UNO (倾斜角度小于椭圆)
        # 椭圆倾斜了 25 度，我们让 UNO 倾斜 15 度
        text_layer = Image.new("RGBA", (width, height), (0,0,0,0))
        t_draw = ImageDraw.Draw(text_layer)
        
        # 使用 font_large
        # 颜色：通常 UNO 牌背的字是白色、黄色或黑色描边。题目没说颜色，但"中间红椭圆"，为了对比度应该是白色或黄色。
        # 保持一致性用白色，带强黑色描边
        t_draw.text((width//2, height//2), "UNO", fill="white", font=font_medium_sym, anchor="mm", stroke_width=8, stroke_fill="black")
        
        text_layer = text_layer.rotate(15, resample=Image.BICUBIC)
        card.paste(text_layer, (0,0), text_layer)
        
        # 角落无显示
        # Do nothing        
    elif value == "Default":
        # Default 卡牌：同 Back 一样显示 UNO 文本
        text_layer = Image.new("RGBA", (width, height), (0,0,0,0))
        t_draw = ImageDraw.Draw(text_layer)
        
        t_draw.text((width//2, height//2), "UNO", fill="white", font=font_medium_sym, anchor="mm", stroke_width=8, stroke_fill="black")
        
        text_layer = text_layer.rotate(15, resample=Image.BICUBIC)
        card.paste(text_layer, (0,0), text_layer)
        
    elif value == "PLAYER":
        # 角色牌
        # 中央绘制 PLAYER - 倾斜 15 度
        
        # 使用稍小的字体以适应长度
        font_player = font_medium
        if len(value) > 4:
            # 如果太长，缩小一点。PLAYER 6个字母，可能需要小一点或者 font_medium (size 180) 是否太大? 
            # 180 可能会超出。
            # 动态调整一下
            try:
                font_player = ImageFont.truetype(font_path, 90)
            except:
                font_player = ImageFont.truetype("arialbd.ttf", 90)

        # 创建文本层
        text_layer = Image.new("RGBA", (width, height), (0,0,0,0))
        t_draw = ImageDraw.Draw(text_layer)
        
        t_draw.text((width//2, height//2), "PLAYER", fill="white", font=font_player, anchor="mm", stroke_width=5, stroke_fill="black")
        
        # 旋转 15 度
        text_layer = text_layer.rotate(15, resample=Image.BICUBIC)
        card.paste(text_layer, (0,0), text_layer)
        
        # 角落绘制: 仅保留 UNO 和 THU 字样
        # 右上角 UNO
        draw.text((width-85, 60), "UNO", fill="white", font=font_label, anchor="mm")
        # 左下角 ONO
        draw.text((85, height-60), "THU", fill="white", font=font_label, anchor="mm")
    elif value == "Skip":
        # 中心绘制禁止符号
        draw_special_symbol(draw, width//2, height//2, "Skip", 200, "white")
        # 还要加个黑色描边效果？稍微难一点，这里先画白色的

        # 角落绘制禁止符号
        draw_special_symbol(draw, 50, 60, "Skip", 50, "white")
        draw_special_symbol(draw, width-50, height-60, "Skip", 50, "white")
        
    elif value == "Reverse":
        # 使用 paste_rotated_layer 来处理中心和角落的旋转
        angle = 25
        
        # 中心绘制反转符号
        paste_rotated_layer(card, width//2, height//2, draw_arrow_symbol, 200, "white", angle)
        
        # 角落绘制反转符号
        paste_rotated_layer(card, 50, 60, draw_arrow_symbol, 50, "white", angle)
        paste_rotated_layer(card, width-50, height-60, draw_arrow_symbol, 50, "white", angle + 180) # 右下角通常也要旋转
        
        # 注意: 右下角如果只是旋转图标，那图标也是斜的。一般 UNO 卡牌右下角是中心对称旋转180度的。 
        # angle + 180 是为了让箭头方向和左上角整体形成180度倒置关系，保持"点对称"感。
        
    elif value == "Wild":
        # Wild 牌
        angle = 25
        # 中心没有文字，但背景已经是四色椭圆 (在前面处理了)
        
        # 角落绘制缩小版四色椭圆
        # 使用 draw_colored_ellipse_symbol, color参数不需要
        paste_rotated_layer(card, 50, 60, draw_colored_ellipse_symbol, 60, "white", angle)
        
        # 右下角 也旋转 180+25 = 205度
        # 注意: draw_colored_ellipse_symbol 里的颜色是固定的。
        # 如果旋转 180 度，颜色的位置也会颠倒 (绿变左上，黄变右上...)
        # 这符合 UNO 牌的一般对称规律 (旋转180度后看起来还是那张牌)
        paste_rotated_layer(card, width-50, height-60, draw_colored_ellipse_symbol, 60, "white", angle + 180)
        
        # 右上角 UNO
        draw.text((width-85, 60), "UNO", fill="white", font=font_label, anchor="mm")
        # 左下角 ONO
        draw.text((85, height-60), "THU", fill="white", font=font_label, anchor="mm")

    elif value == "Back":
        pass # Back 已经处理了，不需要绘制 UNO/THU 和其他东西

    else:
        # 普通数字牌
        draw.text((width//2, height//2), str(value), fill="white", font=font_large, anchor="mm", stroke_width=5, stroke_fill="black")
        draw.text((50, 60), str(value), fill="white", font=font_small, anchor="mm")
        draw.text((width-50, height-60), str(value), fill="white", font=font_small, anchor="mm")
        
        # 右上角 UNO
        draw.text((width-85, 60), "UNO", fill="white", font=font_label, anchor="mm")
        # 左下角 ONO
        draw.text((85, height-60), "THU", fill="white", font=font_label, anchor="mm")

    # 保存图片
    card.save(output_path)
    print(f"卡牌已生成: {output_path}")

def main():
    # 批量生成
    output_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "assets", "cards")
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 清理旧的卡牌目录
    color_dirs = ["red", "blue", "green", "yellow", "black", "misc"]
    for color_dir in color_dirs:
        dir_path = os.path.join(output_dir, color_dir)
        if os.path.exists(dir_path):
            import shutil
            shutil.rmtree(dir_path)
    
    # 重新创建目录
    for color_dir in color_dirs:
        os.makedirs(os.path.join(output_dir, color_dir), exist_ok=True)

    # 1. 生成数字牌 (0-9)
    colors = ["red", "blue", "green", "yellow"]
    for color in colors:
        for num in range(10):
            filename = os.path.join(output_dir, color, f"uno_{color}_{num}.png")
            create_uno_card(color, str(num), filename)

    # 2. 生成功能牌
    special_cards = ["+2", "Skip", "Reverse"]
    for color in colors:
        for card_type in special_cards:
            filename = os.path.join(output_dir, color, f"uno_{color}_{card_type}.png")
            create_uno_card(color, card_type, filename)

    # 3. 生成黑色 +4 牌
    filename = os.path.join(output_dir, "black", "uno_black_+4.png")
    create_uno_card("black", "+4", filename)

    # 4. 生成黑色 Wild 牌
    filename = os.path.join(output_dir, "black", "uno_black_wild.png")
    create_uno_card("black", "Wild", filename)

    # 5. 生成牌背
    filename = os.path.join(output_dir, "misc", "uno_back.png")
    create_uno_card("black", "Back", filename)

    # 6. 生成角色牌
    filename = os.path.join(output_dir, "misc", "uno_player.png")
    create_uno_card("light_brown", "PLAYER", filename)

    # 7. 生成四色 Default 卡牌
    for color in colors:
        filename = os.path.join(output_dir, color, f"uno_{color}_default.png")
        create_uno_card(color, "Default", filename)

    print("所有卡牌生成完毕！")

if __name__ == "__main__":
    main()
