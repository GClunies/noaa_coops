from setuptools import setup
import noaa_coops

setup(name='noaa_coops',
      version='0.1',
      description='Python wrapper to fetch NOAA Tides & Currents Data',
      url='https://github.com/GClunies/noaa_coops',
      author='Greg Clunies',
      author_email='greg.clunies@gmail.com',
      license='GNU GPL',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Intended Audience :: Science/Research',
          'Topic :: Scientific/Engineering',
          'License :: OSI Approved :: GNU GPL License',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
      ],
      packages=['noaa_coops'],
      install_requires=['requests', 'numpy', 'pandas'],
      zip_safe=False)
      
