#!/usr/bin/env python

from setuptools import setup, find_packages
import redbot

setup(name='redbot',
      version=redbot.__version__,
      description='REDbot is lint for HTTP.',
      long_description=open("README.md").read(),
      long_description_content_type="text/markdown",
      author='Mark Nottingham',
      author_email='mnot@mnot.net',
      license = "MIT",
      url='https://redbot.org/project/',
      download_url='http://github.com/mnot/redbot/tarball/redbot-%s' % redbot.__version__,
      packages=find_packages(),
      package_dir={'redbot': 'redbot'},
      scripts=['bin/redbot_cli', 'bin/redbot_daemon.py', 'bin/redbot_cgi.py'],
      package_data={
        'redbot': ['assets/*.css', 'assets/*.js', 'assets/*.map', 'assets/webfonts/*', 'assets/logo/*']
      },
      python_requires=">=3.6",
      install_requires=[
          'thor >= 0.8.0',
          'markdown >= 2.6.5',
          'netaddr >= 0.7.19'
      ],
      extras_require={
          'dev': [
          'mypy',
          'selenium'
          ]
      },
      classifiers=[
        'Programming Language :: Python :: 3.6',
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
