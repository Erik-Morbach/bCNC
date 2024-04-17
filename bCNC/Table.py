import os.path
import csv

class Table:
    def __init__(self, name):
        self.name = name

    def save(self, table:list):
        fields = []
        if len(table)==0: fields = ['index']
        else: fields = table[0].keys()
        for row in table:
            for field in fields:
                if field == 'index': continue
                try:
                    row[field] = "%.03f" % float(row[field])
                except:
                    pass
        flag = 'x'
        if os.path.isfile(self.name): flag = 'w'
        with open(self.name, flag, newline='') as tableFile:
            writer = csv.DictWriter(tableFile,fieldnames=fields, restval=0.000)
            writer.writeheader()
            writer.writerows(table)

    def getTable(self):
        rows = []
        table = []
        with open(self.name, 'r', newline='') as tableFile:
            rows = csv.DictReader(tableFile)
            self.fields = rows.fieldnames
            table = [row for row in rows]
        return table

    def getRow(self, index):
        table = self.getTable()
        for id,w in enumerate(table):
            if int(w['index'])==int(index):
                return w, id
        return None, -1
