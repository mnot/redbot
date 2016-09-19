#!/usr/bin/env python

from distutils.core import setup

setup(name='redbot',
      version='1.0',
      description='Resource Expert Droid',
      author='Mark Nottingham',
      author_email='mnot@mnot.net',
      url='https://redbot.org/project/',
      packages=['redbot',
                'redbot.message',
                'redbot.message.headers',
                'redbot.formatter',
                'redbot.resource',
                'redbot.resource.active_check'
      ],
      package_dir={'redbot': 'redbot'},
      scripts=['bin/redbot'],
      install_requires = [
          'thor >= 0.3.0',
          'markdown >= 2.6.5'
      ],
      classifiers=[
        'Programming Language :: Python'
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',      
      ],
)
