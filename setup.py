#!/usr/bin/env python

from distutils.core import setup

setup(name='redbot',
      version='1.0',
      description='Resource Expert Droid',
      author='Mark Nottingham',
      author_email='mnot@mnot.net',
      url='http://redbot.org/project/',
      packages=['redbot'],
      package_dir={'redbot': 'src'},
      scripts=['scripts/redbot'],
      classifiers=['Programming Language :: Python'],
)
