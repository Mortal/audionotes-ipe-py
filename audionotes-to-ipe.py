import io
import tarfile
import argparse
import plistlib
import subprocess


def write_path(xs, ys, fp, color='black'):
    fp.write('<path stroke="%s" pen="fat">\n' % color)
    for i, (x, y) in enumerate(zip(xs, ys)):
        if i == 0:
            fp.write('%s %s m\n' % (x, y))
        else:
            fp.write('%s %s l\n' % (x, y))
    fp.write('</path>\n')


def str_path(xs, ys, color):
    s = io.StringIO()
    write_path(xs, ys, s, color=' '.join(color))
    return s.getvalue()


def get_points(stroke):
    points = stroke['points']
    xs = points[::2]
    ys = points[1::2]
    ys = [641 - y for y in ys]
    return xs, ys


def write_stroke(stroke, fp):
    xs, ys = get_points(stroke)
    write_path(xs, ys, fp)


def old_stroke_groups(drawing):
    stroke_groups = drawing['strokeGroups']
    # stroke_group = stroke_groups[0]
    p = subprocess.Popen(
        ('xclip', '-selection', 'c'),
        #('cat',),
        stdin=subprocess.PIPE,
        universal_newlines=True)
    strokes = [stroke
               for stroke_group in stroke_groups
               for stroke in stroke_group
               if len(stroke['points']) > 2]
    with p:
        all_xs = []
        all_ys = []
        for stroke in strokes:
            xs, ys = get_points(stroke)
            all_xs += xs
            all_ys += ys
        xpos = (max(all_xs) + min(all_xs)) / 2
        ypos = (max(all_ys) + min(all_ys)) / 2
        p.stdin.write('<ipeselection pos="%d %d">\n' % (xpos, ypos))
        for stroke in strokes:
            write_stroke(stroke, p.stdin)
        p.stdin.write('</ipeselection>\n')
    p.wait()


def brief_stroke_groups(drawing):
    paths = []
    for g in drawing['briefStrokeGroups']:
        # g[0] has "anchorChar" and "anchorYLoc"
        # which I don't know what to do with
        for p in g:
            meta = p['metaStr'].rstrip(',').split(',')
            (_0, _1, _2, _3, time, _5, stroke_width,
             _7, red, green, blue, alpha) = meta
            pts = p['ptsStr'].rstrip(',').split(',')
            xs = [float(x) for x in pts[::2]]
            ys = [-float(y) for y in pts[1::2]]
            color = (red, green, blue)
            paths.append((xs, ys, color))

    min_x = min(x for xs, ys, c in paths for x in xs)
    max_x = max(x for xs, ys, c in paths for x in xs)
    min_y = min(y for xs, ys, c in paths for y in ys)
    max_y = max(y for xs, ys, c in paths for y in ys)

    sx = max_x - min_x
    sy = max_y - min_y

    for xs, ys, c in paths:
        for i, x in enumerate(xs):
            xs[i] = x - min_x
        for i, y in enumerate(ys):
            ys[i] = y - min_y

    cx = sx / 2
    cy = sy / 2

    str_paths = ''.join(str_path(xs, ys, c) for xs, ys, c in paths)
    selection = '<ipeselection pos="%s %s">\n%s</ipeselection>\n' % (
        cx, cy, str_paths)

    print(selection)

    p = subprocess.Popen(
        ('xclip', '-selection', 'c'),
        stdin=subprocess.PIPE,
        universal_newlines=True)
    with p:
        p.communicate(input=selection)
        p.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    args = parser.parse_args()

    with tarfile.open(args.filename, 'r:') as tf:
        names = tf.getnames()
        xml = next(n for n in names if n.endswith('.xml'))
        with tf.extractfile(xml) as fp:
            o = plistlib.load(fp)

    if o['app_version'] != '5.2.1':
        print("Warning: Unknown app version %s" % o['app_version'])

    drawing = o['drawing']
    brief_stroke_groups(drawing)


if __name__ == "__main__":
    main()
