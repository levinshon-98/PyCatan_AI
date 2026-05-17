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
            "colorama>=0.4.0",
            "requests>=2.25.0"  # For streaming broadcaster HTTP calls
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
      entry_points={
          'console_scripts': [
              'pycatan-replay-viewer=examples.ai_testing.replay_viewer:main',
          ],
      },
      zip_safe=False)
