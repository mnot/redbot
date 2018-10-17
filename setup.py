#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='redbot',
      version='1.1',
      description='Resource Expert Droid',
      author='Mark Nottingham',
      author_email='mnot@mnot.net',
      url='https://redbot.org/project/',
      packages=find_packages(),
      package_dir={'redbot': 'redbot'},
      scripts=['bin/redbot', 'bin/redbot_daemon.py', 'bin/redbot_cgi.py'],
      package_data={
        'redbot': ['assets/*.css', 'assets/*.js', 'assets/*.map', 'assets/icon/*', 'assets/logo/*']
      },
      install_requires=[
          'thor >= 0.5.0',
          'markdown >= 2.6.5'
      ],
      extras_require={
          'dev': [
              'mypy',
              'selenium'
          ]
      },
      classifiers=[
        'Programming Language :: Python :: 3.5',
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Environment :: Web Environment',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Testing',
        'Operating System :: Unix',
        'Operating System :: MacOS :: MacOS X',
        'License :: OSI Approved :: MIT License',
      ],
)
