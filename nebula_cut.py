# -*- coding: utf-8 -*-
"""
NEBULA CUT - mobile-first video editor prototype
Requirements:
    pip install kivy
    Install FFmpeg and make sure `ffmpeg` is on PATH for exporting.
Optional video preview backend:
    pip install ffpyplayer

Run:
    python nebula_cut.py

This is an original editor prototype inspired by the supplied dark UI/video references.
It is not a copy of CapCut/Alight Motion/After Effects assets or source code.
"""
import os
import json
import shutil
import subprocess
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.metrics import dp
from kivy.properties import NumericProperty, ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.video import Video
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView

# Portrait layout; Android will use the device's actual screen size.
Window.clearcolor = (0.035, 0.043, 0.075, 1)
Window.softinput_mode = "below_target"

BG = (0.035, 0.043, 0.075, 1)
PANEL = (0.085, 0.10, 0.17, 1)
PANEL2 = (0.12, 0.14, 0.23, 1)
CYAN = (0.20, 0.83, 0.96, 1)
MUTED = (0.57, 0.63, 0.75, 1)
WHITE = (0.92, 0.95, 1, 1)
PURPLE = (0.58, 0.43, 0.96, 1)


def rounded(widget, color=PANEL, radius=14):
    with widget.canvas.before:
        Color(*color)
        widget._bg = RoundedRectangle(pos=widget.pos, size=widget.size,
                                      radius=[dp(radius)])
    widget.bind(pos=lambda *_: setattr(widget._bg, "pos", widget.pos),
                size=lambda *_: setattr(widget._bg, "size", widget.size))
    return widget


class Pill(Button):
    def __init__(self, **kwargs):
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", PANEL2)
        kwargs.setdefault("color", WHITE)
        kwargs.setdefault("font_size", "13sp")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(40))
        super().__init__(**kwargs)


class CurveView(Widget):
    """Visual cubic Bezier easing curve, controlled by two horizontal handles."""
    x1 = NumericProperty(.25)
    y1 = NumericProperty(.10)
    x2 = NumericProperty(.75)
    y2 = NumericProperty(.90)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.redraw, size=self.redraw,
                  x1=self.redraw, y1=self.redraw, x2=self.redraw, y2=self.redraw)

    def redraw(self, *_):
        self.canvas.clear()
        x, y = self.x + dp(12), self.y + dp(12)
        w, h = max(1, self.width - dp(24)), max(1, self.height - dp(24))
        with self.canvas:
            Color(.25, .30, .43, 1)
            Line(rectangle=(x, y, w, h), width=1)
            Color(.23, .29, .42, 1)
            Line(points=[x, y+h/2, x+w, y+h/2], dash_length=dp(4), dash_offset=dp(3))
            Color(*PURPLE)
            Line(points=[x, y, x+w, y+h], width=1.2)
            pts = []
            for i in range(101):
                t = i / 100
                u = 1-t
                bx = 3*u*u*t*self.x1 + 3*u*t*t*self.x2 + t**3
                by = 3*u*u*t*self.y1 + 3*u*t*t*self.y2 + t**3
                pts.extend([x + bx*w, y + by*h])
            Color(*CYAN)
            Line(points=pts, width=2.2)


class EditorApp(App):
    def build(self):
        self.title = "NEBULA CUT"
        self.project = {
            "name": "Untitled Project",
            "clips": [],
            "selected": -1,
            "playhead": 0.0,
            "duration": 0.0,
            "curve": [0.25, 0.10, 0.75, 0.90],
            "effect": "原片",
            "brightness": 0.0,
            "contrast": 1.0,
            "saturation": 1.0,
        }
        self.preview = None
        self.video_path = None
        self.root_ui = BoxLayout(orientation="vertical", spacing=dp(7), padding=dp(8))
        self._build_header()
        self._build_preview()
        self._build_timeline()
        self._build_inspector()
        self._build_toolbar()
        self.refresh_timeline()
        return self.root_ui

    def label(self, text, size=13, color=WHITE, **kwargs):
        return Label(text=text, font_size=f"{size}sp", color=color, **kwargs)

    def _build_header(self):
        bar = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        logo = Label(text="[color=32d4f5]◉[/color]", markup=True,
                     font_size="30sp", size_hint_x=None, width=dp(42))
        bar.add_widget(logo)
        titlebox = BoxLayout(orientation="vertical")
        titlebox.add_widget(self.label("NEBULA CUT", 16, WHITE, bold=True))
        titlebox.add_widget(self.label("移动视频工作室  ·  草稿自动保存在本机", 9, MUTED))
        bar.add_widget(titlebox)
        save = Pill(text="保存项目", size_hint_x=None, width=dp(76))
        save.bind(on_release=lambda *_: self.save_project())
        bar.add_widget(save)
        self.root_ui.add_widget(bar)

    def _build_preview(self):
        self.preview_box = BoxLayout(orientation="vertical", size_hint_y=.37, padding=dp(5))
        rounded(self.preview_box, (0.015, 0.02, 0.045, 1), 18)
        self.preview_label = self.label(
            "NEBULA CUT\n\n导入视频开始创作\n[color=32d4f5]＋ 添加素材[/color]",
            17, WHITE, markup=True, halign="center")
        self.preview_box.add_widget(self.preview_label)
        self.root_ui.add_widget(self.preview_box)

    def _build_timeline(self):
        area = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(164), spacing=dp(5))
        top = BoxLayout(size_hint_y=None, height=dp(30))
        top.add_widget(self.label("时间轴  /  TIMELINE", 12, WHITE, bold=True))
        self.time_label = self.label("00:00.00", 11, CYAN, halign="right")
        top.add_widget(self.time_label)
        area.add_widget(top)
        controls = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(5))
        for text, fn in [("＋ 视频", self.import_video), ("＋ 音频", self.import_audio),
                         ("◇ 关键帧", self.add_keyframe), ("曲线", self.open_curve)]:
            b = Pill(text=text)
            b.bind(on_release=lambda _, f=fn: f())
            controls.add_widget(b)
        area.add_widget(controls)
        self.timeline_scroll = ScrollView(size_hint_y=1, do_scroll_x=True, do_scroll_y=False)
        self.track_box = BoxLayout(size_hint_x=None, width=dp(500), spacing=dp(5), padding=dp(4))
        self.timeline_scroll.add_widget(self.track_box)
        area.add_widget(self.timeline_scroll)
        self.root_ui.add_widget(area)

    def _build_inspector(self):
        self.inspector = BoxLayout(orientation="vertical", size_hint_y=.23, spacing=dp(5))
        row = BoxLayout(size_hint_y=None, height=dp(26))
        row.add_widget(self.label("属性 / 动画", 12, WHITE, bold=True))
        row.add_widget(self.label("选择片段后调整参数", 10, MUTED, halign="right"))
        self.inspector.add_widget(row)
        self.prop_row = BoxLayout(size_hint_y=None, height=dp(43), spacing=dp(5))
        for name, key, lo, hi, step in [
            ("缩放", "scale", .2, 3, .05),
            ("旋转", "rotation", -180, 180, 1),
            ("透明", "opacity", 0, 1, .05),
        ]:
            cell = BoxLayout(orientation="vertical", spacing=0)
            cell.add_widget(self.label(name, 10, MUTED))
            s = Slider(min=lo, max=hi, value=1 if key != "rotation" else 0,
                       step=step)
            s.bind(value=lambda _, v, k=key: self.update_property(k, v))
            cell.add_widget(s)
            self.prop_row.add_widget(cell)
        self.inspector.add_widget(self.prop_row)
        self.root_ui.add_widget(self.inspector)

    def _build_toolbar(self):
        scroll = ScrollView(size_hint_y=None, height=dp(66), do_scroll_x=True, do_scroll_y=False)
        tools = BoxLayout(size_hint_x=None, width=dp(620), spacing=dp(6), padding=(0, dp(3)))
        entries = [
            ("媒体", self.import_video), ("滤镜", self.open_filters),
            ("特效", self.open_effects), ("文字", self.add_text),
            ("关键帧", self.add_keyframe), ("曲线编辑", self.open_curve),
            ("导出", self.export_video),
        ]
        for name, fn in entries:
            b = Pill(text=name, size_hint_x=None, width=dp(82), height=dp(52))
            b.bind(on_release=lambda _, f=fn: f())
            tools.add_widget(b)
        scroll.add_widget(tools)
        self.root_ui.add_widget(scroll)

    def selected_clip(self):
        i = self.project["selected"]
        if 0 <= i < len(self.project["clips"]):
            return self.project["clips"][i]
        return None

    def refresh_timeline(self):
        self.track_box.clear_widgets()
        clips = self.project["clips"]
        if not clips:
            self.track_box.width = dp(500)
            self.track_box.add_widget(self.label("还没有素材  ·  点击「＋ 视频」导入", 12, MUTED))
            return
        totalw = 0
        for i, clip in enumerate(clips):
            w = max(dp(112), min(dp(250), dp(48) * max(2, clip.get("duration", 3))))
            tile = BoxLayout(orientation="vertical", size_hint=(None, 1), width=w, padding=dp(5))
            rounded(tile, CYAN if i == self.project["selected"] else PANEL2, 9)
            tile.add_widget(self.label(("▶ " if clip.get("kind") == "video" else "♫ ") +
                                       clip["name"][:22], 10,
                                       (0.02, .05, .08, 1) if i == self.project["selected"] else WHITE))
            tile.add_widget(self.label(f'{clip.get("duration", 0):.1f}s  ·  {len(clip.get("keyframes", []))} 个关键帧',
                                       9, MUTED))
            choose = Pill(text="选中", height=dp(27))
            choose.bind(on_release=lambda _, idx=i: self.select_clip(idx))
            tile.add_widget(choose)
            self.track_box.add_widget(tile)
            totalw += w + dp(5)
        self.track_box.width = max(dp(500), totalw)

    def select_clip(self, index):
        self.project["selected"] = index
        clip = self.selected_clip()
        if clip and clip["kind"] == "video":
            self.load_preview(clip["path"])
        self.refresh_timeline()

    def load_preview(self, path):
        self.preview_box.clear_widgets()
        try:
            self.preview = Video(source=path, state="pause", options={"eos": "pause"})
            self.preview_box.add_widget(self.preview)
            self.preview_label = None
        except Exception:
            self.preview_box.add_widget(self.label(Path(path).name, 16, WHITE))
        self.video_path = path

    def file_popup(self, title, callback, filters=None):
        chooser = FileChooserListView(path=str(Path.home()), filters=filters or ["*.mp4", "*.mov", "*.mkv", "*.avi", "*.mp3", "*.wav", "*.m4a"])
        layout = BoxLayout(orientation="vertical", spacing=dp(5), padding=dp(6))
        layout.add_widget(chooser)
        buttons = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        pop = Popup(title=title, content=layout, size_hint=(.95, .88))
        cancel = Pill(text="取消")
        ok = Pill(text="导入")
        cancel.bind(on_release=pop.dismiss)
        def confirm(*_):
            if chooser.selection:
                callback(chooser.selection[0])
                pop.dismiss()
        ok.bind(on_release=confirm)
        buttons.add_widget(cancel); buttons.add_widget(ok)
        layout.add_widget(buttons)
        pop.open()

    def probe_duration(self, path):
        if not shutil.which("ffprobe"):
            return 5.0
        try:
            out = subprocess.check_output([
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", path
            ], stderr=subprocess.DEVNULL, timeout=8)
            return max(.1, float(out.decode().strip()))
        except Exception:
            return 5.0

    def import_video(self):
        self.file_popup("选择视频素材", self._add_video, ["*.mp4", "*.mov", "*.mkv", "*.avi", "*.webm"])

    def _add_video(self, path):
        dur = self.probe_duration(path)
        self.project["clips"].append({
            "kind": "video", "path": path, "name": Path(path).name,
            "duration": dur, "scale": 1.0, "rotation": 0.0, "opacity": 1.0,
            "keyframes": [], "text": ""
        })
        self.project["selected"] = len(self.project["clips"]) - 1
        self.project["duration"] += dur
        self.load_preview(path)
        self.refresh_timeline()

    def import_audio(self):
        self.file_popup("选择音频素材", self._add_audio, ["*.mp3", "*.wav", "*.m4a", "*.aac", "*.ogg"])

    def _add_audio(self, path):
        self.project["clips"].append({"kind": "audio", "path": path,
            "name": Path(path).name, "duration": self.probe_duration(path), "keyframes": []})
        self.project["selected"] = len(self.project["clips"]) - 1
        self.refresh_timeline()

    def add_keyframe(self):
        clip = self.selected_clip()
        if not clip:
            self.notice("请先导入并选中一个片段")
            return
        t = float(self.project["playhead"])
        clip.setdefault("keyframes", []).append({
            "time": t, "scale": clip.get("scale", 1.0),
            "rotation": clip.get("rotation", 0.0),
            "opacity": clip.get("opacity", 1.0),
            "x": 0.0, "y": 0.0
        })
        clip["keyframes"].sort(key=lambda k: k["time"])
        self.refresh_timeline()
        self.notice(f"已在 {t:.2f}s 添加关键帧")

    def update_property(self, key, value):
        clip = self.selected_clip()
        if clip:
            clip[key] = round(float(value), 3)

    def open_curve(self):
        clip = self.selected_clip()
        if not clip or len(clip.get("keyframes", [])) < 2:
            self.notice("至少添加两个关键帧，才能编辑它们之间的曲线")
            return
        vals = self.project["curve"]
        body = BoxLayout(orientation="vertical", spacing=dp(9), padding=dp(12))
        graph = CurveView(size_hint_y=.55, x1=vals[0], y1=vals[1], x2=vals[2], y2=vals[3])
        body.add_widget(graph)
        sliders = []
        for title, idx in [("控制点 1 · X", 0), ("控制点 1 · Y", 1),
                           ("控制点 2 · X", 2), ("控制点 2 · Y", 3)]:
            line = BoxLayout(size_hint_y=None, height=dp(35))
            line.add_widget(self.label(title, 11, MUTED))
            sl = Slider(min=0, max=1, value=vals[idx])
            sl.bind(value=lambda _, v, j=idx: self.set_curve_value(graph, j, v))
            sliders.append(sl); line.add_widget(sl); body.add_widget(line)
        done = Pill(text="应用曲线")
        def apply(*_):
            self.project["curve"] = [graph.x1, graph.y1, graph.x2, graph.y2]
            self.notice("贝塞尔缓动曲线已应用")
            pop.dismiss()
        done.bind(on_release=apply); body.add_widget(done)
        pop = Popup(title="关键帧 · 贝塞尔曲线", content=body, size_hint=(.92, .82))
        pop.open()

    def set_curve_value(self, graph, idx, value):
        setattr(graph, ["x1", "y1", "x2", "y2"][idx], value)

    def open_filters(self):
        self.choice_popup("滤镜库", [
            ("原片", "原片"), ("电影青橙", "colorbalance=rs=0.08:bs=0.10:rm=0.02:bm=-0.05"),
            ("冷调蓝", "colorbalance=bs=0.22:bm=0.10"),
            ("复古胶片", "eq=saturation=0.72:contrast=1.12"),
            ("黑白", "hue=s=0"), ("高饱和", "eq=saturation=1.55"),
        ], "滤镜")

    def open_effects(self):
        self.choice_popup("特效库", [
            ("无特效", "原片"), ("梦幻柔光", "gblur=sigma=1.2"),
            ("锐化", "unsharp=5:5:0.8:3:3:0.4"),
            ("暗角", "vignette=PI/5"), ("噪点胶片", "noise=alls=12:allf=t"),
            ("镜像", "hflip"),
        ], "特效")

    def choice_popup(self, title, choices, mode):
        body = GridLayout(cols=2, spacing=dp(7), padding=dp(10), size_hint_y=None)
        body.bind(minimum_height=body.setter("height"))
        pop = Popup(title=title, size_hint=(.9, .65))
        for name, value in choices:
            b = Pill(text=name, height=dp(44))
            def choose(_, v=value, n=name):
                self.project["effect"] = v
                self.notice(f"{mode}已选择：{n}")
                pop.dismiss()
            b.bind(on_release=choose); body.add_widget(b)
        sc = ScrollView(); sc.add_widget(body); pop.content = sc; pop.open()

    def add_text(self):
        clip = self.selected_clip()
        if not clip or clip.get("kind") != "video":
            self.notice("请先选中一个视频片段")
            return
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        ti = TextInput(hint_text="输入要添加的文字", multiline=False, size_hint_y=None, height=dp(45))
        box.add_widget(ti)
        b = Pill(text="应用文字")
        pop = Popup(title="文字图层", content=box, size_hint=(.85, .35))
        def apply(*_):
            clip["text"] = ti.text
            pop.dismiss()
            self.notice("文字已加入片段（导出时烧录）")
        b.bind(on_release=apply); box.add_widget(b); pop.open()

    def export_video(self):
        clip = self.selected_clip()
        if not clip or clip.get("kind") != "video":
            self.notice("请先选中一个视频片段")
            return
        if not shutil.which("ffmpeg"):
            self.notice("没有检测到 FFmpeg：请先安装 FFmpeg 并加入 PATH")
            return
        out = str(Path(clip["path"]).with_name(Path(clip["path"]).stem + "_nebula.mp4"))
        filters = []
        effect = self.project.get("effect", "原片")
        if effect != "原片":
            filters.append(effect)
        filters.append(f"scale=trunc(iw*{clip.get('scale',1):.3f}/2)*2:trunc(ih*{clip.get('scale',1):.3f}/2)*2")
        if clip.get("rotation", 0):
            filters.append(f"rotate={clip['rotation']}*PI/180:ow=rotw(iw):oh=roth(ih)")
        if clip.get("text"):
            safe = clip["text"].replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
            filters.append(f"drawtext=text='{safe}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=h*0.82:box=1:boxcolor=black@0.4")
        cmd = ["ffmpeg", "-y", "-i", clip["path"], "-vf", ",".join(filters),
               "-c:v", "libx264", "-preset", "medium", "-crf", "18",
               "-c:a", "aac", "-b:a", "192k", out]
        self.notice("正在导出，请稍候…")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if result.returncode == 0:
                self.notice("导出成功：" + out)
            else:
                self.notice("导出失败：" + result.stderr[-350:])
        except Exception as e:
            self.notice("导出错误：" + str(e))

    def save_project(self):
        path = Path.home() / "nebula_cut_project.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.project, f, ensure_ascii=False, indent=2)
            self.notice("项目已保存：" + str(path))
        except Exception as e:
            self.notice("保存失败：" + str(e))

    def notice(self, message):
        pop = Popup(title="NEBULA CUT", content=self.label(message, 12, WHITE),
                    size_hint=(.88, .25))
        Clock.schedule_once(lambda *_: pop.dismiss(), 2.8)
        pop.open()


if __name__ == "__main__":
    EditorApp().run()
