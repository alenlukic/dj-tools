from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = [r.strip() for r in f.read().splitlines()]

setup(
    name='dj-tools',
    version='2.3.3',
    description='Tools for DJs: generate informative file/track titles (Camelot code, key, BPM) using ID3 metadata; '
                'display candidate transition matches using playing track Camelot code and BPM.',
    url='https://github.com/alenlukic/dj-tools',
    author='Alen Lukic',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python :: 3'
    ],
    keywords='dj harmonic mixing camelot code audio id3 beatport',
    install_requires=requirements,
    packages=find_packages(),
    python_requires='>=3, <4'
)
