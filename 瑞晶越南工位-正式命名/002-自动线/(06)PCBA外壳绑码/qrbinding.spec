# -*- mode: python ; coding: utf-8 -*-
a = Analysis(['qrbinding.py'], pathex=['..', '../../004-\u624b\u52a8\u7ebf'], binaries=[], datas=[], hiddenimports=['station_scrap_workflow','station_data_sync','station_alarm','station_i18n','station_retest','station_runtime_safety'], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='qrbinding', debug=False, bootloader_ignore_signals=False, strip=False, upx=True, upx_exclude=[], runtime_tmpdir=None, console=False, disable_windowed_traceback=False, argv_emulation=False, target_arch=None, codesign_identity=None, entitlements_file=None, uac_admin=True)
