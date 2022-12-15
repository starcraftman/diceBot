"""
The setup file for packaging DiceBot
"""
from __future__ import absolute_import, print_function

import fnmatch
import glob
import os
import shlex
import subprocess
import sys
import tempfile
from setuptools import setup, find_packages, Command

ROOT = os.path.abspath(os.path.dirname(__file__))
if os.path.dirname(__file__) == '':
    ROOT = os.getcwd()

try:
    input = raw_input
except NameError:
    pass


def make_get_input():
    """
    Simple wrapper to get input from user.
    When --yes in sys.argv, skip input and assume yes to any request.
    """
    default = False
    if '--yes' in sys.argv:
        sys.argv.remove('--yes')
        default = True

    def inner_get_input(msg):
        """
        The actual function that emulates input.
        """
        if default:
            return 'yes'

        return input(msg)
    inner_get_input.default = default

    return inner_get_input


get_input = make_get_input()


def rec_search(wildcard):
    """
    Traverse all subfolders and match files against the wildcard.

    Returns:
        A list of all matching files absolute paths.
    """
    matched = []
    for dirpath, _, files in os.walk(os.getcwd()):
        fn_files = [os.path.join(dirpath, fn_file) for fn_file
                    in fnmatch.filter(files, wildcard)]
        matched.extend(fn_files)
    return matched


class Clean(Command):
    """
    Equivalent of make clean.
    """
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        matched = ' '.join(rec_search('*.pyc'))
        matched += ' ' + ' '.join(glob.glob('*.egg-info') + glob.glob('*.egg'))
        matched += ' ' + ' '.join(rec_search('*diagram.png'))
        cmd = 'rm -vrf .eggs .tox build dist ' + matched
        print('Executing: ' + cmd)
        recv = get_input('OK? y/n  ').strip().lower()
        if recv.startswith('y'):
            subprocess.call(shlex.split(cmd))


class InstallDeps(Command):
    """
    Install dependencies to run & test.
    """
    description = "Install the depencies for the project."
    user_options = [
        ('force=', None, "Bypass prompt."),
    ]

    def initialize_options(self):
        self.force = None

    def finalize_options(self):
        pass

    def run(self):
        print('Installing/Upgrading runtime & testing dependencies')
        cmd = 'pip install -U ' + ' '.join(RUN_DEPS + TEST_DEPS)
        print('Executing: ' + cmd)
        if self.force:
            recv = self.force
        else:
            recv = get_input('OK? y/n  ').strip().lower()
        if recv.startswith('y'):
            out = subprocess.DEVNULL if get_input.default else None
            timeout = 150
            try:
                subprocess.Popen(shlex.split(cmd), stdout=out).wait(timeout)
            except subprocess.TimeoutExpired:
                print('Deps installation took over {} seconds, something is wrong.'.format(timeout))

        try:
            subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            print("ERROR: Cannot find 'ffmpeg' on $PATH. Needed for music player.")

        try:
            subprocess.run(['chromedriver', '--help'], stdout=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            print("""ERROR: Cannot find 'chromedriver' on $PATH.

This is needed for searching commands like !pf
Select the version that matches your installed chromium/chrome version.
Chromedriver Site:
    http://chromedriver.chromium.org/

If you do not have chrome available and want the latest stable use below PPA:
Google Chrome PPA:
    https://www.ubuntuupdates.org/ppa/google_chrome
""")


class Test(Command):
    """
    Run the tests and track coverage.
    """
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def check_prereqs(self):
        """
        Checks required programs.
        """
        tfile = tempfile.NamedTemporaryFile()
        with open(os.devnull, 'w') as dnull:
            with open(tfile.name, 'w') as fout:
                subprocess.Popen(shlex.split('py.test --version'),
                                 stdout=dnull, stderr=fout).wait()
            with open(tfile.name, 'r') as fin:
                out = '\n'.join(fin.readlines())
            if 'pytest-cov' not in out:
                print('Please run: python setup.py deps')
                sys.exit(1)

    def run(self):
        self.check_prereqs()
        old_cwd = os.getcwd()

        try:
            os.chdir(ROOT)
            subprocess.call(shlex.split('py.test --cov=dice'))
        finally:
            os.chdir(old_cwd)


class Coverage(Command):
    """
    Run the tests, generate the coverage html report and open it in your browser.
    """
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def check_prereqs(self):
        """
        Checks required programs.
        """
        tfile = tempfile.NamedTemporaryFile()
        with open(os.devnull, 'w') as dnull:
            with open(tfile.name, 'w') as fout:
                subprocess.Popen(shlex.split('py.test --version'),
                                 stdout=dnull, stderr=fout).wait()
            with open(tfile.name, 'r') as fin:
                out = '\n'.join(fin.readlines())
            if 'pytest-cov' not in out:
                print('Please run: python setup.py deps')
                sys.exit(1)
        try:
            with open(os.devnull, 'w') as dnull:
                subprocess.check_call(shlex.split('coverage --version'), stderr=dnull)
        except subprocess.CalledProcessError:
            print('Please run: python setup.py deps')
            sys.exit(1)

    def run(self):
        self.check_prereqs()
        old_cwd = os.getcwd()
        cov_dir = os.path.join(tempfile.gettempdir(), 'diceCoverage')
        cmds = [
            'py.test --cov=dice --cov=dicedb',
            'coverage html -d ' + cov_dir,
            'xdg-open ' + os.path.join(cov_dir, 'index.html'),
        ]

        try:
            os.chdir(ROOT)
            for cmd in cmds:
                subprocess.call(shlex.split(cmd))
        finally:
            os.chdir(old_cwd)


class UMLDocs(Command):
    """
    Generate UML class and module diagrams.
    """
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def check_prereqs(self):
        """
        Checks required programs.
        """
        try:
            with open(os.devnull, 'w') as dnull:
                subprocess.check_call(shlex.split('pyreverse -h'),
                                      stdout=dnull, stderr=dnull)
        except subprocess.CalledProcessError:
            print('Please run: python setup.py deps')
            sys.exit(1)
        try:
            with open(os.devnull, 'w') as dnull:
                subprocess.check_call(shlex.split('dot -V'),
                                      stdout=dnull, stderr=dnull)
        except OSError:
            print('Missing graphviz library (dot). Please run:')
            print('sudo apt-get install graphviz')
            sys.exit(1)

    def run(self):
        self.check_prereqs()
        old_cwd = os.getcwd()
        cmds = [
            'pyreverse dicedb',
            'dot -Tpng classes.dot -o ./extras/dicedb_class_diagram.png',
            'dot -Tpng packages.dot -o ./extras/dicedb_module_diagram.png',
            'pyreverse dice dicedb',
            'dot -Tpng classes.dot -o ./extras/overall_class_diagram.png',
            'dot -Tpng packages.dot -o ./extras/overall_module_diagram.png',
        ]

        try:
            os.chdir(ROOT)
            for cmd in cmds:
                subprocess.call(shlex.split(cmd))
        finally:
            for fname in glob.glob('*.dot'):
                os.remove(fname)
            os.chdir(old_cwd)

        print('\nDiagrams generated:')
        print('  ' + '\n  '.join(glob.glob('extras/*diagram.png')))


SHORT_DESC = 'Simple Dice Bot for Discord'
MY_NAME = 'Jeremy Pallats / starcraft.man'
MY_EMAIL = 'N/A'
RUN_DEPS = ['argparse', 'bs4', 'certifi', 'decorator', 'discord.py==1.7.3', 'motor', 'numpy',
            'pymysql', 'pynacl', 'pyyaml', 'selenium', 'SQLalchemy',
            'uvloop', 'youtube_dl']
TEST_DEPS = ['coverage', 'flake8', 'aiomock', 'mock', 'pylint', 'pytest', 'pytest-asyncio',
             'pytest-cov', 'sphinx', 'tox']
setup(
    name='diceBot',
    version='0.1.0',
    description=SHORT_DESC,
    long_description=SHORT_DESC,
    url='https://github.com/starcraftman/diceBot',
    author=MY_NAME,
    author_email=MY_EMAIL,
    maintainer=MY_NAME,
    maintainer_email=MY_EMAIL,
    license='BSD',
    platforms=['any'],

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX :: Linux',
        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],

    # What does your project relate to?
    keywords='development',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    # packages=find_packages(exclude=['venv', 'test*']),
    packages=find_packages(exclude=['venv', '.tox']),

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=RUN_DEPS,

    tests_require=TEST_DEPS,

    # # List additional groups of dependencies here (e.g. development
    # # dependencies). You can install these using the following syntax,
    # # for example:
    # # $ pip install -e .[dev,test]
    extras_require={
        'dev': ['pyandoc'],
        'test': TEST_DEPS,
    },

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={
        'console_scripts': [
            'dicebot = dice.bot:main',
        ],
    },

    cmdclass={
        'clean': Clean,
        'coverage': Coverage,
        'deps': InstallDeps,
        'test': Test,
        'uml': UMLDocs,
    }
)
