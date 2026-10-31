[app]
title=星云切割
package.name=nebulacut
package.domain=org.nebulacut
source.dir=。
source.include_exts=py，png，jpg，kv，json
版本=1.0.0
要求=python3，kivy
方向=纵向
全屏=1

安卓。权限=read_EXTERNAL_STORAGE、write_EXTERNAL_STORAGE、READ_MEDIA_VIDEO、READ_MEDIA_AUDIO
android.api=35
android.minapi=23
android.archs=arm64-v8a
android.accept_sdk_license=True

[buildozer]
log_level=2
warn_on_root=1
