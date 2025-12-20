from setuptools import setup, find_packages

setup(name='pycatan',
      version='0.14',
      description='A Python Module for playing The Settlers of Catan',
      url='https://github.com/josefwaller/PyCatan',
      long_description=open("readme.md").read(),
      long_description_content_type='text/markdown',
      author='Josef Waller',
      author_email='josef@siriusapplications.com',
      license='MIT',
      install_requires=[
            "flask>=2.0.0",
            "colorama>=0.4.0"
      ],
      packages=find_packages(),
      package_data={
          'pycatan': [
              'config/data/*.json',
              'static/css/*.css',
              'static/js/*.js',
              'templates/*.html'
          ]
      },
      include_package_data=True,
      zip_safe=False)
