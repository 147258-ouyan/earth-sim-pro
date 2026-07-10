import PyInstaller.__main__

PyInstaller.__main__.run([
    'run_app.py',
    '--name=地球模拟器Pro++',
    '--onefile',
    '--add-data=app.py;.',
    '--add-data=earth_sim;earth_sim',
    '--add-data=historical_data_real.csv;.',
    '--clean',
    '--noconfirm',
])