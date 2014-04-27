import os
import sys

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(
    name="Jerbminer",
    version="0.0.1",
    author="Ford Peprah",
    author_email="user@example.com",
    packages=['jobmine'],
    scripts=['bin/jobmine'],
    url="http://github.com/hkpeprah/jerbminer",
    license="LICENSE",
    package_data={
        'jobmine': ['resources/*']
    },
    description="Jerbminer provides a script (and GUI application) for interfacing with the University of Waterloo's Jobmine system.",
    long_description="Jerbminer provides a script (and GUI application) for interfacing with the University of Waterloo's Jobmine system.  Jobmine is a web application developed by the University of Waterloo to help students with the coop process.  This script/application is in no way affiliated with the University of Waterloo and is the side project of one student.",
    install_requires=map(lambda t: t.strip(),
                         open(
                             os.path.join(
                                 os.path.dirname(__file__), 'requirements.txt'), 'r').readlines())
)
