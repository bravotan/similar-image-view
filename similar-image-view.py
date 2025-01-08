#!/usr/bin/env python3

from traceback import print_exc
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PIL import Image
import imagehash
from tools.image_hash_connection import Connection as IHC


class Item:
    def __init__(self, path):
        self.pixmap = QPixmap(path).scaledToHeight(200)
        self.path = path


class CustomListModel(QAbstractListModel):
    layoutChanged = pyqtSignal()  # layoutChanged シグナルをカスタムモデルに追加

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = []
        self.fetch()

    def rowCount(self, parent=None):
        return len(self.items)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and index.isValid():
            return self.items[index.row()].path[:20]
        elif role == Qt.ItemDataRole.DecorationRole and index.isValid():
            return self.items[index.row()].pixmap

    def fetch(self, path=None):
        self.items = []
        with IHC() as ihc:
            try:
                if path:
                    ihc.cursor.execute('SELECT hash FROM images where image_path = %s', (path ,))
                    ihash = ihc.cursor.fetchone()[0]
                    ihc.cursor.execute('SELECT image_path, BIT_COUNT(%s ^ hash) AS hamming_distance FROM images ORDER BY hamming_distance LIMIT 20 OFFSET 0', (ihash ,))
                else:
                    ihc.cursor.execute('SELECT image_path FROM images LIMIT 20 OFFSET 0')
            except Exception as e:
                print_exc()
            for path in ihc.cursor.fetchall():
                self.items.append(Item(path[0]))

    def fetch_hash(self, ihash):
        self.items = []
        with IHC() as ihc:
            try:
                ihc.cursor.execute('SELECT image_path, BIT_COUNT(%s ^ hash) AS hamming_distance FROM images ORDER BY hamming_distance LIMIT 20 OFFSET 0', (ihash ,))
            except Exception as e:
                print_exc()
            for path in ihc.cursor.fetchall():
                self.items.append(Item(path[0]))

    def setCurrentItem(self, index):
        #print(index, index.row())
        self.fetch(self.items[index.row()].path)
        self.dataChanged.emit(self.index(0, 0), self.index(len(self.items) - 1, 0))

    def reverse_items(self):
        #print("befor", self.items)
        self.layoutAboutToBeChanged.emit()  # レイアウトが変更される前にシグナルを発行
        self.items.reverse()
        self.layoutChanged.emit()  # レイアウト変更後にシグナルを発行
        #print("after", self.items)
        self.dataChanged.emit(self.index(0, 0), self.index(len(self.items) - 1, 0))


# https://chatgpt.com/share/675cce2c-b66c-8007-8ca4-f6e8bb96d674
class CustomListView(QListView):
    def __init__(self, parent=None):
        super().__init__(parent)
        #self.setDragDropMode(QAbstractItemView.InternalMove)
        #self.setDragEnabled(True)
        #self.setDropIndicatorShown(True)
        self.setAcceptDrops(True)
        self.contextMenuItems = [
            (self.copyPath,),
        ]
    
    # def mousePressEvent(self, event: QMouseEvent):
    #     # クリック時に選択をクリア
    #     if event.button() == Qt.MouseButton.LeftButton:
    #         self.clearSelection()  # 選択を解除

    #     # 通常の処理も継続
    #     super().mousePressEvent(event)

    def copyPath(self):
        "Copy file path"
        indexes = self.selectedIndexes()
        if len(indexes) == 0:
            return
        index = indexes[0]
        print(self.model().items[index.row()].path)

    def contextMenuEvent(self, event):
        contextMenu = QMenu(self)
        contextMenu.addSeparator()
        index = self.indexAt(event.pos())
        if not index.isValid():
            return
        # TODO: multi selection?
        self.selectionModel().select(index, self.selectionModel().SelectionFlag.ClearAndSelect)

        for i, funcs in enumerate(self.contextMenuItems):
            if i > 0:
                contextMenu.addSeparator()
            for func in funcs:
                a = contextMenu.addAction(func.__doc__)
                a.triggered.connect(func)
                #a.setEnabled(False)
            
        contextMenu.exec(event.globalPos())

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
        
    def dragMoveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                imhash = imagehash.average_hash(Image.open(path))
                ihash = int(''.join(str(b) for b in 1 * imhash.hash.flatten()), 2)
                model = self.model()
                self.clearSelection()
                model.fetch_hash(ihash)
                model.dataChanged.emit(model.index(0, 0), model.index(len(model.items) - 1, 0))
                
                break
            event.accept()
        else:
            event.ignore()

       
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        il = [f'Item {i+1}' for i in range(100)]
        self.model = CustomListModel(il)

        self.listView = CustomListView()
        self.listView.setModel(self.model)
        self.listView.setViewMode(QListView.ViewMode.IconMode)
        self.listView.setSelectionMode(QListView.SelectionMode.MultiSelection)
        #self.listView.setSelectionBehavior(QListView.SelectionBehavior.SelectItems)
        self.listView.doubleClicked.connect(self.changeItem)

        layout = QVBoxLayout()
        layout.addWidget(self.listView)

        #self.button = QPushButton("Reverse Items")
        #self.button.clicked.connect(self.reverse_items)
        #layout.addWidget(self.button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def changeItem(self, index):
        self.model.setCurrentItem(index)
        self.listView.clearSelection()

    #def reverse_items(self):
    #    self.model.reverse_items()


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.resize(app.primaryScreen().size() * .5)
    window.show()
    app.exec()
