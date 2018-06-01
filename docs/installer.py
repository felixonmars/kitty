#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
import platform
import re
import sys
import tempfile

py3 = sys.version_info[0] > 2
is64bit = platform.architecture()[0] == '64bit'
is_macos = 'darwin' in sys.platform.lower()

try:
    __file__
    from_file = True
except NameError:
    from_file = False

if py3:
    unicode = str
    raw_input = input
    # from urllib.parse import urlparse
    import urllib.request as urllib

    def encode_for_subprocess(x):
        return x
else:
    from future_builtins import map  # noqa
    # from urlparse import urlparse
    import urllib2 as urllib

    def encode_for_subprocess(x):
        if isinstance(x, unicode):
            x = x.encode('utf-8')
        return x


class Reporter:  # {{{

    def __init__(self, fname):
        self.fname = fname
        self.last_percent = 0

    def __call__(self, blocks, block_size, total_size):
        percent = (blocks*block_size)/float(total_size)
        report = '\rDownloaded {:.1%}         '.format(percent)
        if percent - self.last_percent > 0.05:
            self.last_percent = percent
            print(report, end='')
# }}}


def get_latest_release_data():
    print('Checking for latest release on GitHub...')
    req = urllib.Request('https://api.github.com/repos/kovidgoyal/kitty/releases/latest', headers={'Accept': 'application/vnd.github.v3+json'})
    res = urllib.urlopen(req)
    data = json.load(res)
    html_url = data['html_url'].replace('/tag/', '/download/').rstrip('/')
    for asset in data.get('assets', ()):
        name = asset['name']
        if is_macos:
            if name.endswith('.dmg'):
                return html_url + '/' + name, asset['size']
        else:
            if name.endswith('.txz'):
                if is64bit:
                    if name.endswith('-x86_64.txz'):
                        return html_url + '/' + name, asset['size']
                else:
                    if name.endswith('-i686.txz'):
                        return html_url + '/' + name, asset['size']
    raise SystemExit('Failed to find the installer package on github')


def do_download(url, size, dest):
    print('Will download and install', os.path.basename(dest))
    reporter = Reporter(os.path.basename(dest))

    # Get content length and check if range is supported
    rq = urllib.urlopen(url)
    headers = rq.info()
    sent_size = int(headers['content-length'])
    if sent_size != size:
        raise SystemExit('Failed to download from {} Content-Length ({}) != {}'.format(url, sent_size, size))
    with open(dest, 'wb') as f:
        while f.tell() < size:
            raw = rq.read(8192)
            if not raw:
                break
            f.write(raw)
            reporter(f.tell(), 1, size)
    rq.close()
    if os.path.getsize(dest) < size:
        raise SystemExit('Download failed, try again later')
    print('\rDownloaded {} bytes'.format(os.path.getsize(dest)))


def clean_cache(cache, fname):
    for x in os.listdir(cache):
        if fname not in x:
            os.remove(os.path.join(cache, x))


def download_installer(url, size):
    fname = url.rpartition('/')[-1]
    tdir = tempfile.gettempdir()
    cache = os.path.join(tdir, 'kitty-installer-cache')
    if not os.path.exists(cache):
        os.makedirs(cache)
    clean_cache(cache, fname)
    dest = os.path.join(cache, fname)
    if os.path.exists(dest) and os.path.getsize(dest) == size:
        print('Using previously downloaded', fname)
        return open(dest, 'rb').read()
    if os.path.exists(dest):
        os.remove(dest)
    raw = do_download(url, size, dest)
    return raw


def main():
    machine = os.uname()[4]
    if machine and machine.lower().startswith('arm'):
        raise SystemExit(
            'You are running on an ARM system. The kitty binaries are only'
            ' available for x86 systems. You will have to build from'
            ' source.')
    url, size = get_latest_release_data()
    download_installer(url, size)


def update_intaller_wrapper():
    # To run: python3 -c "import runpy; runpy.run_path('installer.py', run_name='update_wrapper')"
    src = open(__file__, 'rb').read().decode('utf-8')
    wrapper = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'installer.sh')
    with open(wrapper, 'r+b') as f:
        raw = f.read().decode('utf-8')
        nraw = re.sub(r'^# HEREDOC_START.+^# HEREDOC_END', lambda m: '# HEREDOC_START\n{}\n# HEREDOC_END'.format(src), raw, flags=re.MULTILINE | re.DOTALL)
        if 'update_intaller_wrapper()' not in nraw:
            raise SystemExit('regex substitute of HEREDOC failed')
        f.seek(0), f.truncate()
        f.write(nraw.encode('utf-8'))


if __name__ == '__main__' and from_file:
    main()
elif __name__ == 'update_wrapper':
    update_intaller_wrapper()