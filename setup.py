from setuptools import setup
import noaa_coops

# Read the contents of README.md file
from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(name='noaa_coops',
      version='0.1.3',
      description='Python wrapper for NOAA Tides & Currents Data and Metadata',
      long_description=long_description,
      long_description_content_type='text/markdown',
      url='https://github.com/GClunies/noaa_coops',
      author='Greg Clunies',
      author_email='greg.clunies@gmail.com',
      license='GNU GPL',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Intended Audience :: Science/Research',
          'Topic :: Scientific/Engineering',
          'License :: OSI Approved :: GNU General Public License v3 (GPLv3)', 
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
      ],
      packages=['noaa_coops'],
      install_requires=['requests', 'numpy', 'pandas'],
      zip_safe=False)
      
