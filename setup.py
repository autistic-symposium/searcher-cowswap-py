from setuptools import setup, find_packages

setup(
    name="cowsol",
    version='1.0',
    packages=find_packages(include=['src', \
                    'src.apis', \
                    'src.strategies', \
                    'src.util']),
    author="steinkirch",
    install_requires=['python-dotenv', 'requests'],
    entry_points={
        'console_scripts': ['cowsol=src.main:run']
    },
)