import setuptools

setuptools.setup(name='mana',
      version='0.1',
      description='xUML Model Analyzer by translating Model data into a Datalog representation',
      url='https://github.com/erik-soederholm/model-analyzer.git',
      author='Erik Söderholm',
      author_email='acerik@gmail.com',
      license='MIT',
      packages=setuptools.find_packages(),
      zip_safe=False,
      install_requires=["pathlib", "flatland", "Jinja2"],
      entry_points={
            "console_scripts": [
                  "mana=mana.__main__:main"
                  ]
            })
