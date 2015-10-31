import io
import os
import tarfile
import argparse
import plistlib
import textwrap
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


def get_ipe_code(drawing, cx=None, cy=None):
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
            if len(xs) > 1:
                paths.append((xs, ys, color))

    min_x = min(x for xs, ys, c in paths for x in xs)
    max_x = max(x for xs, ys, c in paths for x in xs)
    min_y = min(y for xs, ys, c in paths for y in ys)
    max_y = max(y for xs, ys, c in paths for y in ys)

    sx = max_x - min_x
    sy = max_y - min_y

    if cx is None:
        cx = sx / 2
        cy = sy / 2

    for xs, ys, c in paths:
        for i, x in enumerate(xs):
            xs[i] = x - min_x - sx / 2 + cx
        for i, y in enumerate(ys):
            ys[i] = y - min_y - sy / 2 + cy

    str_paths = ''.join(str_path(xs, ys, c) for xs, ys, c in paths)
    return str_paths, cx, cy


def brief_stroke_groups(drawing):
    str_paths, cx, cy = get_ipe_code(drawing)
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
    parser.add_argument('--output-sound', '-s', required=False)
    parser.add_argument('--output-page', '-p', required=False)
    parser.add_argument('--output-rtf', '-r', required=False)
    args = parser.parse_args()

    with tarfile.open(args.filename, 'r:') as tf:
        names = tf.getnames()
        xml = next(n for n in names if n.endswith('.xml'))
        with tf.extractfile(xml) as fp:
            o = plistlib.load(fp)

    if o['app_version'] != '5.2.1':
        print("Warning: Unknown app version %s" % o['app_version'])

    drawing = o['drawing']
    # brief_stroke_groups(drawing)

    if args.output_sound:
        base, ext = os.path.splitext(args.output_sound)
        cmdline = ('ffmpeg',)
        with tarfile.open(args.filename, 'r:') as tf:
            for i, filename in enumerate(o['recordFileNames']):
                tarinfo = tf.getmember(filename)
                partname = base + '_%d.caf' % i
                cmdline += ('-i', partname)
                tf._extract_member(tarinfo, partname)
        if ext == '.mp3':
            cmdline += ('-acodec', 'libmp3lame', '-q:a', '5')
        cmdline += (args.output_sound,)
        subprocess.check_call(cmdline)

    if args.output_page:
        base, ext = os.path.splitext(args.output_page)
        cx2, cy2 = 595, 842
        str_paths, cx, cy = get_ipe_code(drawing, cx2 / 2, cy2 / 2)
        with open(base + '.ipe', 'w') as fp:
            fp.write(textwrap.dedent("""
                <?xml version="1.0"?>
                <!DOCTYPE ipe SYSTEM "ipe.dtd">
                <ipe version="70005" creator="Ipe 7.1.4">
                <info created="D:20151031152507" modified="D:20151031152507"/>
                <ipestyle name="basic">
                <pen name="fat" value="1.2"/>
                <layout crop="no"/>
                </ipestyle>
                <page>
                <layer name="alpha"/>
                <view layers="alpha" active="alpha"/>
            """.strip() + '\n'))
            fp.write(str_paths)
            fp.write('</page>\n</ipe>\n')

        if ext != '.ipe':
            subprocess.check_call(
                ('ipetoipe', '-' + ext.lstrip('.'),
                 base + '.ipe', base + ext))

    if args.output_rtf:
        with open(args.output_rtf, 'wb') as fp:
            fp.write(o['RTFData'])


if __name__ == "__main__":
    main()
