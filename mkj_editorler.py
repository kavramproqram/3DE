#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MKJ Editörler — editör koleksiyonu + uygulama girişi
====================================================

Bu dosya ÇALIŞTIRILAN dosyadır:   python3 mkj_editorler.py [dosya.mkj]

  mkj_pencere.py ........ Blender tarzı alan (pencere) sistemi
  mkj_editorler.py ...... editörler + bunları pencere sistemine bağlayan ana pencere
  mkj_cube_draw.py ...... mevcut uygulama (sahne, 3B görünüm, dosya işlemleri)

Editörler (her alanın başlığındaki simgeye tıklayarak değiştirilir)
  3B Görünüm ..... asıl çizim alanı (tek örnek; başka alandan seçilirse yer değiştirir)
  Küp Editörü .... piksel editörü; seçili küpü CANLI düzenler (Kaydet gerekmez)
  Kitaplık ....... küpler; tıkla = seç, Ctrl+tık = karışıma ekle
  Özellikler ..... araç, oyun modu düğmesi, fırça ve karışım ayarları
  Sahne Listesi .. sahnede hangi küpten kaç tane olduğu

Hepsi aynı sahneyi paylaşır: kitaplıkta küp seçince küp editörü o küpü açar,
piksel çizince 3B görünüm anında güncellenir.
Sistem yalnızca küplerden oluşur; başka nesne türü yoktur.
SPACE: oyun modu (görünmez küre ile küpler üzerinde süzülme).
"""
import os
import sys
import json
import uuid
import traceback

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame,
    QLabel, QPushButton, QScrollArea, QListWidget, QListWidgetItem,
    QDoubleSpinBox, QSpinBox, QComboBox, QMenu
)
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap, QIcon, QPolygonF, QSurfaceFormat
from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal

from mkj_cube_draw import (
    MainWindow, CubeEditorDialog, CubeListWidget, Cube, MIX_MODES, btn_style,
    MENU_STYLE, apply_dark_palette,
    SETTINGS_PATH, CFG_DIR, APP_NAME
)
from mkj_pencere import AreaManager, EditorRegistry, EditorType

DEFAULT_IDS = ["viewport", "cube_editor", "library", "properties"]


# ----------------------------------------------------------------------------
# Simgeler (kodla çizilir)
# ----------------------------------------------------------------------------
def make_icon(kind, size=18):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor("#e0e0e0"), 1.4))
    s = float(size)
    if kind == "viewport":
        c = s / 2
        top = [QPointF(c, 2), QPointF(s - 2, s * 0.30), QPointF(c, s * 0.52), QPointF(2, s * 0.30)]
        left = [QPointF(2, s * 0.30), QPointF(c, s * 0.52), QPointF(c, s - 2), QPointF(2, s * 0.72)]
        right = [QPointF(s - 2, s * 0.30), QPointF(c, s * 0.52), QPointF(c, s - 2), QPointF(s - 2, s * 0.72)]
        p.setBrush(QColor("#8fb8ff")); p.drawPolygon(QPolygonF(top))
        p.setBrush(QColor("#4a7bd0")); p.drawPolygon(QPolygonF(left))
        p.setBrush(QColor("#2f56a0")); p.drawPolygon(QPolygonF(right))
    elif kind == "cube_editor":
        n = 4
        cs = (s - 4) / n
        cols = ["#e06c6c", "#e0c46c", "#6ce08a", "#6cb0e0"]
        for y in range(n):
            for x in range(n):
                p.setBrush(QColor(cols[(x + y) % 4]) if (x + y) % 2 == 0 else QColor("#444"))
                p.drawRect(QRectF(2 + x * cs, 2 + y * cs, cs, cs))
    elif kind == "library":
        h = (s - 6) / 2
        for i, col in enumerate(("#d0d0d0", "#6fa8dc", "#e69138", "#93c47d")):
            x, y = i % 2, i // 2
            p.setBrush(QColor(col))
            p.drawRoundedRect(QRectF(2 + x * (h + 2), 2 + y * (h + 2), h, h), 2, 2)
    elif kind == "properties":
        for i, (ky, kx) in enumerate(((0.25, 0.65), (0.5, 0.3), (0.75, 0.55))):
            y = s * ky
            p.drawLine(QPointF(2, y), QPointF(s - 2, y))
            p.setBrush(QColor("#ffb347"))
            p.drawEllipse(QPointF(s * kx, y), 2.4, 2.4)
    elif kind == "outliner":
        for i, ind in enumerate((0, 4, 4, 0)):
            y = s * (0.2 + i * 0.2)
            p.setBrush(QColor("#9bd")); p.drawEllipse(QPointF(3 + ind, y), 1.6, 1.6)
            p.drawLine(QPointF(7 + ind, y), QPointF(s - 2, y))
    p.end()
    return QIcon(pm)


# ----------------------------------------------------------------------------
# Ortak: ana pencere durum sinyaline yavaşlatılmış (debounce) bağlanma
# ----------------------------------------------------------------------------
class SyncMixin:
    def _init_sync(self, win):
        self.win = win
        self._sync_dirty = False
        self._sync_timer = QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(60)
        self._sync_timer.timeout.connect(self._do_sync_safe)
        win.sync.connect(self.schedule_sync)

    def schedule_sync(self):
        if self.isVisible():
            self._sync_timer.start()
        else:
            self._sync_dirty = True

    def showEvent(self, e):
        super().showEvent(e)
        if self._sync_dirty:
            self._sync_dirty = False
            self._sync_timer.start()

    def _do_sync_safe(self):
        try:
            self.do_sync()
        except Exception:
            traceback.print_exc()

    def do_sync(self):
        pass


def _title(text):
    l = QLabel(text)
    l.setStyleSheet("color:#9aa;font-weight:bold;padding:6px 2px 2px 2px;")
    return l


# ----------------------------------------------------------------------------
# KÜP EDİTÖRÜ — mevcut CubeEditorDialog'un gömülü, canlı sürümü
# ----------------------------------------------------------------------------
class CubeEditorPanel(SyncMixin, CubeEditorDialog):
    _live = False

    def __init__(self, win):
        cid = win.brush_ids[0] if win.brush_ids else win.order[0]
        cube = win.scene.cubes[cid]
        # Pikseller küpün kendi görüntülerine çizilir -> değişiklik anında kalıcıdır.
        super().__init__(win, cube.faces, cube.name, True, parent=None)
        self.setWindowFlags(Qt.Widget)
        self.cube_id = cid
        self.preview.setMinimumHeight(120)
        for b in self.findChildren(QPushButton):
            b.setAutoDefault(False)
            b.setDefault(False)
            t = b.text()
            if t in ("Kaydet", "İptal", "Listeye Ekle"):
                b.hide()
            elif t == "Yeni Küp Olarak Ekle":
                b.setText("Kopyasını Listeye Ekle")
        self._commit_timer = QTimer(self)
        self._commit_timer.setSingleShot(True)
        self._commit_timer.setInterval(25)
        self._commit_timer.timeout.connect(self._commit)
        self.name_edit.textChanged.connect(self._rename)
        self._init_sync(win)
        self._live = True

    # Gömülü olduğu için diyalog kapanmaz; ayarlar sadece ana pencereye yazılır.
    def accept(self):
        pass

    def reject(self):
        pass

    def _ok(self):
        pass

    def done(self, r):
        self._push_settings()

    def _push_settings(self):
        w = self.win
        w.mix_colors = [QColor(c) for c in self.mix_colors]
        w.mix_history = self.mix_history
        w.ed_mix_mode = self.mix_mode
        w.ed_mix_angle = self.mix_angle

    def update_labels(self):
        super().update_labels()
        if self._live:
            self._push_settings()
            self.win.schedule_save()

    def refresh_preview(self):
        super().refresh_preview()
        if self._live:
            self._commit_timer.start()

    def _commit(self):
        w = self.win
        cube = w.scene.cubes.get(self.cube_id)
        if cube is None:
            return
        w.scene.register_cube(cube)       # atlas dokusunu günceller
        w.invalidate_thumb(cube.id)
        w.modified = True
        w.update_title()
        w.schedule_save()
        w.viewport.update()

    def _rename(self, text):
        if not self._live:
            return
        cube = self.win.scene.cubes.get(self.cube_id)
        if cube is not None:
            cube.name = text.strip() or cube.name
            self.win.schedule_save()

    def _ok_new(self):
        cube = self.win.scene.cubes.get(self.cube_id)
        if cube is None:
            return
        new = Cube(uuid.uuid4().hex[:12], cube.name + " kopya", [f.copy() for f in self.faces])
        self.win.add_cube(new)            # yeni küp seçilir -> editör ona geçer

    def load_cube(self, cid):
        cube = self.win.scene.cubes.get(cid)
        if cube is None:
            return
        self._live = False
        self.cube_id = cid
        self.faces = cube.faces
        self.name_edit.setText(cube.name)
        self.preview.set_faces(self.faces)
        self.canvas.update()
        self._live = True

    def do_sync(self):
        w = self.win
        ref = w.brush_ids[0] if w.brush_ids else None
        if ref and ref in w.scene.cubes and ref != self.cube_id:
            self.load_cube(ref)


def _make_cube_editor(win):
    panel = CubeEditorPanel(win)
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.NoFrame)
    sa.setWidget(panel)
    sa.panel = panel
    return sa


# ----------------------------------------------------------------------------
# KİTAPLIK
# ----------------------------------------------------------------------------
class LibraryEditor(SyncMixin, QWidget):
    def __init__(self, win):
        super().__init__()
        self._init_sync(win)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        row = QHBoxLayout()
        lab = QLabel("Küpler")
        lab.setStyleSheet("color:#9aa;font-weight:bold;")
        row.addWidget(lab, 1)
        b1 = QPushButton("＋ Küp")
        b1.setToolTip("Seçili küpün kopyasını yeni küp olarak ekle")
        b1.clicked.connect(self.new_cube)
        for b in (b1,):
            b.setStyleSheet(btn_style(False, 12))
            b.setFocusPolicy(Qt.NoFocus)
            row.addWidget(b)
        lay.addLayout(row)
        self.list = CubeListWidget(win, cols=6, size=48)
        self.list.picked.connect(win.select_cube)
        self.list.context.connect(win.cube_context_menu)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.list)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        lay.addWidget(self.scroll, 1)
        hint = QLabel("Sol tık: seç · Ctrl+tık: karışıma ekle · Sağ tık: seçenekler")
        hint.setStyleSheet("color:#777;font-size:11px;")
        hint.setWordWrap(True)
        lay.addWidget(hint)

    def new_cube(self):
        w = self.win
        src = w.brush_ids[0] if w.brush_ids else w.order[0]
        base = w.scene.cubes[src]
        w.add_cube(Cube(uuid.uuid4().hex[:12], "Küp %d" % (len(w.order) + 1), base.copy_faces()))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cell = self.list.size + self.list.gap
        cols = max(1, (self.scroll.viewport().width() - 2 * self.list.pad) // cell)
        if cols != self.list.cols:
            self.list.cols = cols
            self.list.refresh()

    def do_sync(self):
        self.list.refresh()


# ----------------------------------------------------------------------------
# ÖZELLİKLER
# ----------------------------------------------------------------------------
class PropertiesEditor(SyncMixin, QWidget):
    def __init__(self, win):
        super().__init__()
        self._init_sync(win)
        self._busy = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        outer.addWidget(sa)
        inner = QWidget()
        sa.setWidget(inner)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(8, 4, 8, 8)

        lay.addWidget(_title("Araç"))
        row = QHBoxLayout()
        self.tool_btns = {}
        for key, label in (("draw", "Çiz"), ("erase", "Sil"), ("paint", "Boya")):
            b = QPushButton(label)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _c=False, k=key: win.set_tool(k))
            row.addWidget(b)
            self.tool_btns[key] = b
        lay.addLayout(row)

        lay.addWidget(_title("Oyun modu"))
        self.fly_btn = QPushButton("Süzülen küre  [Space]")
        self.fly_btn.setFocusPolicy(Qt.NoFocus)
        self.fly_btn.setToolTip("Görünmez küre olarak küplerin üzerinde süzül (Space ile aç/kapa)")
        self.fly_btn.clicked.connect(win.toggle_fly)
        lay.addWidget(self.fly_btn)
        hint = QLabel("W/A/S/D: süzül · Shift: hızlı · Fare sürükle: bak\n"
                      "Küplerin dışına çıkarsan geri döner.")
        hint.setStyleSheet("color:#777;font-size:11px;")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        lay.addWidget(_title("Fırça"))
        self.brush_label = QLabel("")
        self.brush_label.setStyleSheet("color:#ddd;")
        lay.addWidget(self.brush_label)
        grid = QGridLayout()
        grid.addWidget(QLabel("Karışım:"), 0, 0)
        self.mix_combo = QComboBox()
        for label, key in MIX_MODES:
            self.mix_combo.addItem(label, key)
        self.mix_combo.activated.connect(self._mix_chosen)
        grid.addWidget(self.mix_combo, 0, 1)
        grid.addWidget(QLabel("Açı:"), 1, 0)
        self.angle = QSpinBox()
        self.angle.setRange(0, 359)
        self.angle.setWrapping(True)
        self.angle.setSingleStep(15)
        self.angle.setSuffix("°")
        self.angle.valueChanged.connect(self._angle_changed)
        grid.addWidget(self.angle, 1, 1)
        lay.addLayout(grid)
        lay.addStretch(1)
        self.do_sync()

    def _mix_chosen(self, idx):
        self.win._set_mix_mode(self.mix_combo.itemData(idx))

    def _angle_changed(self, v):
        if self._busy:
            return
        self.win.mix_angle = int(v)
        self.win.update_mix_labels()

    def do_sync(self):
        w = self.win
        self._busy = True
        try:
            for k, b in self.tool_btns.items():
                b.setStyleSheet(btn_style(k == w.tool, 13))
            self.fly_btn.setStyleSheet(btn_style(w.viewport.fly_active(), 13))
            self.brush_label.setText("Fırça: " + (w.brush_name(w.brush_ids[0]) if w.brush_ids else "-")
                                     + (" +%d" % (len(w.brush_ids) - 1) if len(w.brush_ids) > 1 else ""))
            i = self.mix_combo.findData(w.mix_mode)
            if i >= 0:
                self.mix_combo.setCurrentIndex(i)
            self.angle.setValue(int(w.mix_angle))
        finally:
            self._busy = False


# ----------------------------------------------------------------------------
# SAHNE LİSTESİ — hangi küpten kaç tane kullanıldığı
# ----------------------------------------------------------------------------
class OutlinerEditor(SyncMixin, QWidget):
    def __init__(self, win):
        super().__init__()
        self._init_sync(win)
        self._busy = False
        self._sig = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.info = QLabel("")
        self.info.setStyleSheet("color:#9aa;")
        lay.addWidget(self.info)
        self.list = QListWidget()
        self.list.itemClicked.connect(self._picked)
        lay.addWidget(self.list, 1)
        hint = QLabel("Tıkla: o küpü fırça yap")
        hint.setStyleSheet("color:#777;font-size:11px;")
        lay.addWidget(hint)

    def _picked(self, item):
        cid = item.data(Qt.UserRole)
        if cid:
            self.win.select_cube(cid)

    def do_sync(self):
        w = self.win
        sig = (w.scene.rev, len(w.order), tuple(w.brush_ids))
        if sig == self._sig:
            return
        self._sig = sig
        counts = {}
        for bid in w.scene.world.values():
            counts[bid] = counts.get(bid, 0) + 1
        self.list.clear()
        for bid, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            cube = w.scene.cubes.get(bid)
            if cube is None:
                continue
            it = QListWidgetItem(QIcon(w.thumb(bid, 28)), "%s   ×%d" % (cube.name, n))
            it.setData(Qt.UserRole, bid)
            self.list.addItem(it)
        self.info.setText("Toplam küp: %d · Küp türü: %d" % (len(w.scene.world), len(counts)))


# ----------------------------------------------------------------------------
# Kayıt defteri
# ----------------------------------------------------------------------------
def build_registry():
    reg = EditorRegistry(fallback="properties")
    reg.register(EditorType("viewport", "3B Görünüm", make_icon("viewport"),
                            lambda win: win.viewport, unique=True))
    reg.register(EditorType("cube_editor", "Küp Editörü", make_icon("cube_editor"), _make_cube_editor))
    reg.register(EditorType("library", "Kitaplık", make_icon("library"), LibraryEditor))
    reg.register(EditorType("properties", "Özellikler", make_icon("properties"), PropertiesEditor))
    reg.register(EditorType("outliner", "Sahne Listesi", make_icon("outliner"), OutlinerEditor))
    return reg


# ----------------------------------------------------------------------------
# Ana pencere: mevcut MainWindow + alan sistemi
# ----------------------------------------------------------------------------
class WorkspaceWindow(MainWindow):
    sync = pyqtSignal()      # editörlere "durum değişti" haberi

    def _build_ui(self):
        super()._build_ui()                      # üst çubuk, boya çubuğu, 3B görünüm, durum çubuğu
        lay = self.layout()
        idx = lay.indexOf(self.viewport)
        lay.removeWidget(self.viewport)
        self.viewport.hide()
        self.workspace = AreaManager(build_registry(), self)
        self.workspace.default_ids = list(DEFAULT_IDS)
        lay.insertWidget(idx, self.workspace, 1)
        self.workspace.build_default(DEFAULT_IDS)
        try:
            saved = self._read_settings().get("workspace")
            if saved:
                self.workspace.load_dict(saved)
        except Exception:
            traceback.print_exc()
            self.workspace.build_default(DEFAULT_IDS)
        try:
            menu = self.file_button.menu()
            menu.addSeparator()
            menu.addAction("Pencere düzenini sıfırla").triggered.connect(self.workspace.reset_layout)
        except Exception:
            pass

    # editörleri bilgilendiren üst sınıf çağrıları
    def update_status(self):
        super().update_status()
        self.sync.emit()

    def refresh_lists(self):
        super().refresh_lists()
        self.sync.emit()

    def invalidate_thumb(self, ref):
        super().invalidate_thumb(ref)
        self.sync.emit()

    def set_tool(self, t):
        super().set_tool(t)
        self.sync.emit()

    # düzen kaydı
    def _read_settings(self):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_layout(self):
        try:
            d = self._read_settings()
            d["workspace"] = self.workspace.to_dict()
            os.makedirs(CFG_DIR, exist_ok=True)
            tmp = SETTINGS_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
            os.replace(tmp, SETTINGS_PATH)
        except Exception:
            traceback.print_exc()

    def closeEvent(self, e):
        super().closeEvent(e)
        if e.isAccepted():
            self._save_layout()


def main():
    sys.excepthook = lambda t, v, tb: traceback.print_exception(t, v, tb)
    fmt = QSurfaceFormat()
    fmt.setVersion(2, 1)
    fmt.setDepthBufferSize(24)
    fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    apply_dark_palette(app)
    win = WorkspaceWindow()
    win.show()
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        win.load_path(sys.argv[1])
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
