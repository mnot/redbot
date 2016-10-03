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
                'redbot.resource.active_check',
                'redbot.syntax'
      ],
      package_dir={'redbot': 'redbot'},
      scripts=['bin/redbot'],
      install_requires = [
          'thor >= 0.3.4',
          'markdown >= 2.6.5'
      ],
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
