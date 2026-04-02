
# outliner_group_popup.py

"""
FINAL STABLE VERSION (NO AUTO ACTIONS)

✔ Find works ONLY on button
✔ No hidden triggers
✔ No auto move EVER
✔ Fully safe UI
✔ Production-ready behavior

Maya 2025+
"""

# -----------------------------
# Qt Import
# -----------------------------
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

import maya.cmds as cmds


# -----------------------------
# ICONS
# -----------------------------
VISIBLE_ICON = ":/visible.png"
HIDDEN_ICON = ":/hidden.png"

LOCK_ICON = ":/lock.png"
UNLOCK_ICON = ":/lockOff.png"


# -----------------------------
# UTILS
# -----------------------------

def is_group(obj):
    return not cmds.listRelatives(obj, shapes=True, fullPath=True)


def get_root_groups():
    return [r for r in cmds.ls(assemblies=True, long=True) if is_group(r)]


def get_children_groups(node):
    children = cmds.listRelatives(node, children=True, type='transform', fullPath=True) or []
    return [c for c in children if is_group(c)]


def get_selected_geometry():
    selection = cmds.ls(selection=True, type='transform', long=True)
    result = []

    for obj in selection:
        shapes = cmds.listRelatives(obj, shapes=True, fullPath=True)
        if shapes and cmds.nodeType(shapes[0]) == 'mesh':
            result.append(obj)

    return result


def get_parent_group(node):
    parent = cmds.listRelatives(node, parent=True, fullPath=True)
    return parent[0] if parent else None


# -----------------------------
# ACTIONS
# -----------------------------

def move_to_group(group):
    selection = get_selected_geometry()
    if not selection:
        cmds.warning("No valid geometry selected.")
        return

    cmds.parent(selection, group, absolute=True)


def create_group():
    result = cmds.promptDialog(title="Create Group", message="Name:", button=["OK", "Cancel"])
    if result == "OK":
        name = cmds.promptDialog(query=True, text=True)
        return cmds.group(empty=True, name=name) if name else cmds.group(empty=True)
    return cmds.group(empty=True)


def rename_group(node):
    short = node.split("|")[-1]
    result = cmds.promptDialog(title="Rename", message="New name:", text=short, button=["OK", "Cancel"])
    if result == "OK":
        new = cmds.promptDialog(query=True, text=True)
        if new:
            return cmds.rename(node, new)
    return node


# -----------------------------
# VISIBILITY / LOCK
# -----------------------------

def is_visible(node):
    try:
        return cmds.getAttr(node + ".visibility")
    except:
        return True


def toggle_visibility(node):
    try:
        cmds.setAttr(node + ".visibility", not cmds.getAttr(node + ".visibility"))
    except:
        pass


def is_locked(node):
    try:
        return cmds.getAttr(node + ".overrideEnabled") == 1 and cmds.getAttr(node + ".overrideDisplayType") == 2
    except:
        return False


def toggle_lock(node):
    try:
        if is_locked(node):
            cmds.setAttr(node + ".overrideEnabled", 0)
        else:
            cmds.setAttr(node + ".overrideEnabled", 1)
            cmds.setAttr(node + ".overrideDisplayType", 2)
    except:
        pass


def get_lock_icon(locked):
    return QtGui.QIcon(LOCK_ICON if locked else UNLOCK_ICON)


# -----------------------------
# UI
# -----------------------------

class OutlinerGroupPopup(QtWidgets.QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowFlags(QtCore.Qt.Tool)
        self.resize(500, 600)

        # 🔒 protection flags
        self.block_find = True
        self.is_processing = False
        self.highlighted_item = None

        layout = QtWidgets.QVBoxLayout(self)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search...")
        layout.addWidget(self.search)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderHidden(True)

        header = self.tree.header()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)

        layout.addWidget(self.tree)

        btn_layout = QtWidgets.QHBoxLayout()

        self.create_btn = QtWidgets.QPushButton("Create")
        self.rename_btn = QtWidgets.QPushButton("Rename")
        self.select_btn = QtWidgets.QPushButton("Select Group")
        self.find_btn = QtWidgets.QPushButton("Find Group")

        btn_layout.addWidget(self.create_btn)
        btn_layout.addWidget(self.rename_btn)
        btn_layout.addWidget(self.select_btn)
        btn_layout.addWidget(self.find_btn)

        layout.addLayout(btn_layout)

        self.move_btn = QtWidgets.QPushButton("Move")
        layout.addWidget(self.move_btn)

        self.build_tree()

        # enable find AFTER UI fully ready
        QtCore.QTimer.singleShot(0, self.enable_find)

        # signals
        self.search.textChanged.connect(self.filter_tree)
        self.tree.itemClicked.connect(self.on_click)

        self.move_btn.clicked.connect(self.move)
        self.create_btn.clicked.connect(self.create)
        self.rename_btn.clicked.connect(self.rename)
        self.select_btn.clicked.connect(self.select_group)
        self.find_btn.clicked.connect(lambda: self.find_group())

    # -----------------------------
    # SAFETY
    # -----------------------------

    def enable_find(self):
        self.block_find = False

    # -----------------------------
    # TREE
    # -----------------------------

    def build_tree(self):
        self.tree.clear()
        for r in get_root_groups():
            self.add_item(None, r)

    def add_item(self, parent, node):
        item = QtWidgets.QTreeWidgetItem()
        item.setText(0, node.split("|")[-1])
        item.setData(0, QtCore.Qt.UserRole, node)

        item.setIcon(1, QtGui.QIcon(VISIBLE_ICON if is_visible(node) else HIDDEN_ICON))
        item.setIcon(2, get_lock_icon(is_locked(node)))

        if parent:
            parent.addChild(item)
        else:
            self.tree.addTopLevelItem(item)

        for c in get_children_groups(node):
            self.add_item(item, c)

    # -----------------------------
    # HIGHLIGHT
    # -----------------------------

    def clear_highlight(self):
        if self.highlighted_item:
            for c in range(self.tree.columnCount()):
                self.highlighted_item.setBackground(c, QtGui.QBrush())
        self.highlighted_item = None

    def find_item(self, node):
        def walk(item):
            if item.data(0, QtCore.Qt.UserRole) == node:
                return item
            for i in range(item.childCount()):
                r = walk(item.child(i))
                if r:
                    return r
            return None

        for i in range(self.tree.topLevelItemCount()):
            r = walk(self.tree.topLevelItem(i))
            if r:
                return r
        return None

    def find_group(self):
        if self.block_find:
            return

        sender = self.sender()
        if sender != self.find_btn:
            return

        sel = cmds.ls(selection=True, long=True)
        if not sel:
            return

        parent = get_parent_group(sel[0])
        if not parent:
            return

        item = self.find_item(parent)
        if not item:
            return

        self.clear_highlight()

        cur = item
        while cur:
            cur.setExpanded(True)
            cur = cur.parent()

        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)

        brush = QtGui.QBrush(QtGui.QColor(80, 140, 255, 120))
        for c in range(self.tree.columnCount()):
            item.setBackground(c, brush)

        self.highlighted_item = item

    # -----------------------------
    # ACTIONS
    # -----------------------------

    def on_click(self, item, column):
        self.clear_highlight()

        node = item.data(0, QtCore.Qt.UserRole)

        if column == 1:
            toggle_visibility(node)
            item.setIcon(1, QtGui.QIcon(VISIBLE_ICON if is_visible(node) else HIDDEN_ICON))

        elif column == 2:
            toggle_lock(node)
            item.setIcon(2, get_lock_icon(is_locked(node)))

    def move(self, *args):
        if self.is_processing:
            return

        self.is_processing = True

        try:
            item = self.tree.currentItem()
            if not item:
                return

            selection = get_selected_geometry()
            if not selection:
                cmds.warning("Nothing selected to move.")
                return

            move_to_group(item.data(0, QtCore.Qt.UserRole))

        finally:
            self.is_processing = False

    def select_group(self):
        item = self.tree.currentItem()
        if item:
            cmds.select(item.data(0, QtCore.Qt.UserRole), hierarchy=True)

    def create(self):
        create_group()
        self.build_tree()

    def rename(self):
        item = self.tree.currentItem()
        if item:
            rename_group(item.data(0, QtCore.Qt.UserRole))
            self.build_tree()

    # -----------------------------
    # SEARCH
    # -----------------------------

    def filter_tree(self, text):
        text = text.lower()

        def match(item):
            visible = text in item.text(0).lower()
            for i in range(item.childCount()):
                if match(item.child(i)):
                    visible = True
            item.setHidden(not visible)
            return visible

        for i in range(self.tree.topLevelItemCount()):
            match(self.tree.topLevelItem(i))

    # -----------------------------
    # KEYS
    # -----------------------------

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()


# -----------------------------
# RUN
# -----------------------------

_popup = None


def show_popup():
    global _popup

    try:
        if _popup:
            _popup.close()
    except:
        pass

    _popup = OutlinerGroupPopup()
    _popup.move(QtGui.QCursor.pos())
    _popup.show()
