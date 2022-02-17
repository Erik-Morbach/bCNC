import CNCList
from numpy import sqrt


def find_line(app, current_x=0, current_y=0):
    if app.gcode.filename == "":
        return 0
    answer = 0
    minimum_error = CNCList.MAXINT
    lines = []
    for block in app.gcode.blocks:
        for line in block:
            lines += [line]
    x_value = current_x - CNCList.MAXINT
    y_value = current_y - CNCList.MAXINT
    for (i, currentLine) in enumerate(lines):
        x_value, y_value = compute_coordinates(x_value, y_value, currentLine)

        dist = (x_value - current_x) ** 2 + (y_value - current_y) ** 2
        dist = sqrt(dist)
        print("{},{} -> {},{} found {}".format(current_x, current_y, x_value, y_value, dist))
        if dist < minimum_error:
            minimum_error = dist
            answer = i
    print("from file {} line {} = {}".format(app.gcode.filename, answer, lines[answer]))
    return answer


def compute_coordinates(current_x, current_y, line):
    def nextNumber(actual_line, index):
        value = ""
        for w in actual_line[index:]:
            if w.isdigit() or w == '.':
                value += w
            else:
                break
        try:
            return float(value)
        except ValueError:
            print("Error in Code")
            return -CNCList.MAXINT

    line = line.upper()
    index_x = line.find('X')
    index_y = line.find('Y')
    if index_x >= 0:
        current_x = nextNumber(line, index_x + 1)
    if index_y >= 0:
        current_y = nextNumber(line, index_y + 1)
    return current_x, current_y
