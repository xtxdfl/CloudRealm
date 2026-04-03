#!/usr/bin/env python3
"""
高级跨平台终端着色系统
支持 256 色、True Color、主题自定义、颜色继承和动态渲染
适配所有主流终端和操作系统
"""

import os
import sys
import platform
from typing import Union, Dict, Any, Optional, Callable

# 终端能力自动检测
class TerminalCapabilityDetector:
    """终端特性检测器，自动识别颜色支持级别"""
    
    def __init__(self):
        self.capabilities = self.detect_capabilities()
        
    def detect_capabilities(self) -> Dict[str, bool]:
        """综合检测终端颜色支持能力"""
        term = os.environ.get('TERM', '')
        colorterm = os.environ.get('COLORTERM', '')
        is_windows = platform.system().lower() == "windows"
        
        return {
            # 基础颜色支持
            '256color_supported': '256color' in term or is_windows,
            'truecolor_supported': 'truecolor' in colorterm.lower() or '24bit' in colorterm.lower(),
            
            # 终端类型检测
            'is_vscode': 'vscode' in term.lower(),
            'is_jetbrains': 'jetbrains' in os.environ.get('TERMINAL_EMULATOR', ''),
            'is_windows_terminal': 'WT_SESSION' in os.environ,
            'is_tmux': 'TMUX' in os.environ,
            'is_screen': 'STY' in os.environ,
            
            # 操作系统检测
            'is_linux': platform.system().lower() == "linux",
            'is_macos': platform.system().lower() == "darwin",
            'is_windows': is_windows,
            
            # 交互式和管道检测
            'is_tty': sys.stdout.isatty(),
            'is_piped': not sys.stdout.isatty() or 'NO_COLOR' in os.environ
        }
    
    @property
    def color_enabled(self) -> bool:
        """颜色功能是否启用"""
        return self.capabilities['is_tty'] and 'NO_COLOR' not in os.environ
    
    @property
    def color_level(self) -> int:
        """获取颜色支持级别: 0=无, 1=16色, 2=256色, 3=真彩"""
        if not self.color_enabled:
            return 0
        if self.capabilities['truecolor_supported']:
            return 3
        if self.capabilities['256color_supported']:
            return 2
        return 1  # 默认16色支持
    
    def __str__(self) -> str:
        """终端特性调试信息"""
        cap_str = []
        for k, v in self.capabilities.items():
            cap_str.append(f"{k.capitalize()}: {'Yes' if v else 'No'}")
        cap_str.append(f"Color level: {self.color_level}")
        return "\n".join(cap_str)


# 创建全局检测器实例
terminal = TerminalCapabilityDetector()

# 主题配置预设
DEFAULT_THEME = {
    # 基础色彩
    "reset": "0",
    "bold": "1",
    "dim": "2",
    "italic": "3",
    "underline": "4",
    "inverse": "7",
    
    # 标准16色
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
    "light_black": "90",
    "light_red": "91",
    "light_green": "92",
    "light_yellow": "93",
    "light_blue": "94",
    "light_magenta": "95",
    "light_cyan": "96",
    "light_white": "97",
    
    # 背景色扩展
    "bg_black": "40",
    "bg_red": "41",
    "bg_green": "42",
    "bg_yellow": "43",
    "bg_blue": "44",
    "bg_magenta": "45",
    "bg_cyan": "46",
    "bg_white": "47",
    "bg_light_black": "100",
    "bg_light_red": "101",
    "bg_light_green": "102",
    "bg_light_yellow": "103",
    "bg_light_blue": "104",
    "bg_light_magenta": "105",
    "bg_light_cyan": "106",
    "bg_light_white": "107",
    
    # 语义化颜色别名
    "success": "32;1",
    "warning": "33;1",
    "error": "31;1",
    "info": "36;1",
    "highlight": "1;93",
    "debug": "2;37"
}

HIGH_CONTRAST_THEME = DEFAULT_THEME.copy()
HIGH_CONTRAST_THEME.update({
    "success": "1;32",    # 亮绿色
    "warning": "1;33",    # 亮黄色
    "error": "1;31",      # 亮红色
    "info": "1;36",       # 亮青色
    "highlight": "1;97",  # 亮白色
})

DARK_MODE_THEME = DEFAULT_THEME.copy()
DARK_MODE_THEME.update({
    "black": "38;5;235",
    "white": "38;5;250",
    "light_black": "38;5;240",
    "light_white": "38;5;255",
    "highlight": "1;38;5;221",
    "success": "38;5;157",
    "warning": "38;5;227",
    "error": "38;5;203",
})


class ColorPresets:
    """
    终端色彩预设管理器
    支持动态切换主题和自定义色盘
    """
    
    def __init__(self, theme: Optional[Dict[str, str]] = None):
        self.theme = theme or DEFAULT_THEME
        self.rgb_cache: Dict[str, str] = {}
        self.palette = self.generate_256_palette()
        self.theme_variants = {
            "default": DEFAULT_THEME,
            "high_contrast": HIGH_CONTRAST_THEME,
            "dark_mode": DARK_MODE_THEME
        }
    
    def generate_256_palette(self) -> Dict[str, int]:
        """生成256色模式的颜色索引映射"""
        return {f"color{i}": i for i in range(1, 256)}
    
    def hex_to_xterm(self, hex_color: str) -> int:
        """
        将十六进制颜色转换为最接近的256色索引值
        算法：欧几里得距离法找到最近色
        """
        if hex_color in self.rgb_cache:
            return int(self.rgb_cache[hex_color])
        
        # 移除#号并转换为RGB
        hex_color = hex_color.lstrip("#")
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        # 16色基础映射（保留0-15为系统颜色）
        closest_index = -1
        min_distance = float('inf')
        
        # 在216色空间（16-231）和24灰度（232-255）中查找
        for r in range(6):
            for g in range(6):
                for b in range(6):
                    index = 16 + 36 * r + 6 * g + b
                    color_r = 55 + r * 40 if r > 0 else 0
                    color_g = 55 + g * 40 if g > 0 else 0
                    color_b = 55 + b * 40 if b > 0 else 0
                    
                    distance = sum((c1 - c2) ** 2 for c1, c2 in zip((color_r, color_g, color_b), rgb))
                    
                    if distance < min_distance:
                        min_distance = distance
                        closest_index = index
        
        # 检查灰度空间（232-255）
        for gray_level in range(24):
            index = 232 + gray_level
            gray_value = 8 + 10 * gray_level
            
            # 计算灰度平方差
            gray_distance = sum((val - gray_value) ** 2 for val in rgb)
            
            if gray_distance < min_distance:
                min_distance = gray_distance
                closest_index = index
        
        self.rgb_cache[f"#{hex_color}"] = str(closest_index)
        return closest_index
    
    def switch_theme(self, theme_name: str) -> None:
        """
        切换预设色彩主题
        :param theme_name: 主题名称 ('default', 'high_contrast', 'dark_mode')
        """
        if theme_name in self.theme_variants:
            self.theme = self.theme_variants[theme_name]
        else:
            theme_options = ', '.join(self.theme_variants.keys())
            raise ValueError(f"无效主题名称 '{theme_name}'。可用选项: {theme_options}")
    
    def define_color(self, name: str, value: Union[str, int]) -> None:
        """
        定义自定义颜色
        :param name: 颜色名称
        :param value: 可以是16色代码、256色索引、RGB十六进制值
        """
        if isinstance(value, str) and value.startswith('#'):
            # RGB十六进制颜色（映射到256色）
            value = self.hex_to_xterm(value)
        
        self.theme[name] = str(value)
    
    def __getattr__(self, name: str) -> str:
        """动态获取颜色代码"""
        if name not in self.theme:
            # 尝试从256色调色板查找
            if name.startswith("color") and name[5:].isdigit():
                index = int(name[5:])
                if 1 <= index <= 255:
                    return f"38;5;{index}"
            
            # 尝试解析RGB格式
            if name.startswith("rgb_") and len(name) > 4:
                parts = name[4:].split('_')
                if len(parts) == 3 and all(p.isdigit() for p in parts):
                    return f"38;2;{';'.join(parts)}"
            
            # 尝试查找调色板
            if name in self.palette:
                return f"38;5;{self.palette[name]}"
            
            raise AttributeError(f"未定义的色彩名称: '{name}'")
        
        return f"\033[{self.theme[name]}m"
    
    def get_code(self, style: str) -> str:
        """获取特定样式的ANSI转义序列"""
        if not terminal.color_enabled:
            return ""
        
        # 支持链式样式: "bold yellow underline"
        codes = []
        for part in style.split():
            if part in self.theme:
                if ';' in self.theme[part]:
                    codes.extend(self.theme[part].split(';'))
                else:
                    codes.append(self.theme[part])
            elif hasattr(self, part):
                code = self.__getattr__(part)
                codes.append(code.split(';')[0].lstrip("\033["))
            else:
                codes.append(part)
        
        # 过滤无效代码
        valid_codes = [c for c in codes if c.isdigit()]
        return f"\033[{';'.join(valid_codes)}m" if valid_codes else ""


# 全局颜色预设实例
colors = ColorPresets()

# 高级文本渲染器
def style(text: str, *styles: str, reset: bool = True) -> str:
    """
    多级文本样式渲染
    :param text: 要渲染的文本
    :param styles: 一个或多个样式名称
    :param reset: 是否添加重置序列
    :return: 带样式的文本
    
    示例: style("重要信息", "bold", "red") -> 红色的粗体文本
    """
    if not terminal.color_enabled or not styles:
        return text
    
    code = colors.get_code(" ".join(styles))
    reset_code = colors.get_code("reset") if reset else ""
    
    # 避免在空字符串上添加样式
    return f"{code}{text}{reset_code}" if text else text


def gradient_text(text: str, start_hex: str, end_hex: str) -> str:
    """
    为文本创建渐变色效果
    :param text: 输入文本
    :param start_hex: 起始颜色（十六进制）
    :param end_hex: 结束颜色（十六进制）
    :return: 渐变着色的文本
    """
    if not terminal.color_enabled or terminal.color_level < 3:
        # 非真彩模式回退到单色
        return style(text, "bold", "rgb_255_0_0")
    
    if len(text) == 0:
        return ""
    
    # 转换十六进制颜色为RGB
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip("#")
        return [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
    
    start_rgb = hex_to_rgb(start_hex)
    end_rgb = hex_to_rgb(end_hex)
    
    # 计算步长
    steps = len(text)
    delta = [(end - start) / (steps - 1) for start, end in zip(start_rgb, end_rgb)]
    
    # 为每个字符生成颜色
    result = []
    for i, char in enumerate(text):
        if char == " ":  # 空格不应用颜色
            result.append(char)
            continue
        
        r = int(start_rgb[0] + delta[0] * i)
        g = int(start_rgb[1] + delta[1] * i)
        b = int(start_rgb[2] + delta[2] * i)
        
        if terminal.color_level == 3:  # True Color
            result.append(f"\033[38;2;{r};{g};{b}m{char}")
        else:  # 降级到256色
            hex_val = f"#{r:02x}{g:02x}{b:02x}"
            xterm_index = colors.hex_to_xterm(hex_val)
            result.append(f"\033[38;5;{xterm_index}m{char}")
    
    return "".join(result) + (colors.get_code("reset") if text else "")


# 上下文管理器模板
class StyledContext:
    """
    带样式的输出上下文管理器
    退出上下文时自动重置文本样式
    """
    
    def __init__(self, *styles: str, outfile=sys.stdout):
        self.styles = styles
        self.outfile = outfile
    
    def __enter__(self):
        """应用文本样式"""
        if self.styles and terminal.color_enabled:
            style_code = colors.get_code(" ".join(self.styles))
            self.outfile.write(style_code)
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        """重置文本样式"""
        if self.styles and terminal.color_enabled:
            reset_code = colors.get_code("reset")
            self.outfile.write(reset_code)
            self.outfile.flush()


# 面向对象的终端输出类
class TerminalPrinter:
    """增强型终端输出器，支持样式继承和模板渲染"""
    
    def __init__(
        self,
        outfile=sys.stdout,
        primary_style: str = "",
        secondary_style: str = "dim",
        error_style: str = "red bold"
    ):
        self.outfile = outfile
        self.primary_style = primary_style
        self.secondary_style = secondary_style
        self.error_style = error_style
        self.indent_level = 0
        self.indent_width = 2
        self.theme_name = "default"
    
    def set_theme(self, theme_name: str) -> None:
        """设置输出主题"""
        try:
            colors.switch_theme(theme_name)
            self.theme_name = theme_name
        except ValueError as e:
            self.error(str(e))
            
            # 尝试恢复默认主题
            colors.switch_theme("default")
            self.theme_name = "default"
    
    def print(
        self,
        *values: Any,
        style: Optional[str] = None,
        sep: str = " ",
        end: str = "\n",
        indent: bool = False
    ):
        """
        样式化输出文本
        :param values: 要输出的值
        :param style: 应用自定义样式
        :param sep: 分隔符
        :param end: 行结束符
        :param indent: 是否应用缩进
        """
        if not values:
            self.outfile.write(end)
            return
        
        # 处理缩进
        prefix = " " * self.indent_level * self.indent_width if indent else ""
        
        # 拼接文本
        text = sep.join(str(v) for v in values)
        
        # 样式化文本
        styled_text = self._apply_style(text, style)
        self.outfile.write(f"{prefix}{styled_text}{end}")
        self.outfile.flush()
    
    def _apply_style(self, text: str, style: Optional[str]) -> str:
        """应用样式，支持样式继承"""
        if not terminal.color_enabled:
            return text
        
        if not style:
            return style(text, self.primary_style)  # 使用默认主样式
        
        # 继承处理（如果样式包含+前缀）
        if style.startswith("+"):
            base_style = self.primary_style
            new_style = style.lstrip("+")
            combined_style = f"{base_style} {new_style}" if base_style else new_style
            return colors.get_code(combined_style) + text + colors.get_code("reset")
        
        return colors.get_code(style) + text + colors.get_code("reset")
    
    def section(self, title: str, level: int = 1) -> StyledContext:
        """
        创建带样式的内容部分
        :param title: 部分标题
        :param level: 标题层级(1-3)
        :return: 用于with语句的上下文管理器
        """
        styles = ["bold"]
        
        # 根据层级选择颜色
        if level == 1:
            styles.append(colors.success)
            section_char = "="
        elif level == 2:
            styles.append(colors.info)
            section_char = "-"
        else:
            styles.append(colors.light_white)
            section_char = "·"
        
        header = f" {title} ".center(40, section_char)
        self.print(header, style=" ".join(styles))
        self.indent_level += level
        return StyledContext(*styles, outfile=self.outfile)
    
    def info(self, *values: Any) -> None:
        """信息级输出"""
        self.print(*values, style="+info", indent=True)
    
    def success(self, *values: Any) -> None:
        """成功信息输出"""
        self.print("✓", *values, style="+success", indent=True)
    
    def warn(self, *values: Any) -> None:
        """警告信息输出"""
        self.print("⚠", *values, style="+warning", indent=True)
    
    def error(self, *values: Any) -> None:
        """错误信息输出"""
        self.print("✕", *values, style=self.error_style, indent=True)
    
    def indent(self, amount: int = 1) -> None:
        """增加缩进级别"""
        self.indent_level += amount
    
    def dedent(self, amount: int = 1) -> None:
        """减少缩进级别"""
        self.indent_level = max(0, self.indent_level - amount)
    
    def __call__(self, *args: Any, **kwargs: Any) -> None:
        """调用快捷方式"""
        self.print(*args, **kwargs)


# 初始化全局打印机实例
console = TerminalPrinter()

# 用法示例
if __name__ == "__main__":
    # 展示终端检测信息
    console.print("终端兼容性报告:", style="bold blue")
    console.info(str(terminal))
    
    # 主题展示
    for theme_name in ["default", "high_contrast", "dark_mode"]:
        colors.switch_theme(theme_name)
        with console.section(f"{theme_name.replace('_', ' ').title()} 主题演示", level=1):
            console.print("普通文本")
            console.print("成功消息", style="success")
            console.print("警告信息", style="warning")
            console.print("错误提醒", style="error")
            console.print("突出显示", style="highlight")
            console.print(f"256色演示", style="bold color135")
            console.print("渐变文本演示:", end=" ")
            console.print(gradient_text("彩虹效果文本", "#FF0000", "#0000FF"), "\n")
    
    # 高级主题用法
    colors.define_color("special_purple", "#8A2BE2")  # 定义紫色
    with console.section("自定义颜色演示", level=2):
        console.print("自定义紫色文本", style="special_purple bold")
        
        # 使用RGB值
        console.print("直接RGB颜色", style="rgb_255_165_0 bold")
        
        # 链式调用
        colors.define_color("fancy_header", "bold underline rgb_50_200_150")
        console.print("花哨标题", style="fancy_header")

# 兼容性导出
if not terminal.color_enabled:
    # 禁用所有颜色输出
    GREEN = RED = BOLD = NO_COLOR = ""
else:
    # 基础颜色兼容别名
    GREEN = colors.green
    RED = colors.red
    BOLD = colors.bold
    NO_COLOR = colors.reset
