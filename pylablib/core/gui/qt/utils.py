import sip

def delete_layout_item(layout, idx):
    if layout:
        item=layout.takeAt(idx)
        layout.removeItem(item)
        if item.layout():
            clean_layout(item.layout())
        if item.widget():
            clean_layout(item.widget().layout())
            item.widget().deleteLater()

def clean_layout(layout, delete_layout=False):
    if layout:
        while layout.count():
            delete_layout_item(layout,0)
        if delete_layout:
            sip.delete(layout)