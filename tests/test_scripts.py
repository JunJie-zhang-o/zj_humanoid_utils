



from zjh_utils.deploy import AutoDeploy, VersionDescription





version = VersionDescription.load("/home/zhangjunjie/Pictures/33-zj_humanoid/src/zjh_utils/resources/versions/test/v1.1.0.json")


print(version.PICO.scripts.post_install)

for script in version.PICO.scripts.post_install:
    print(script)
    script.execute()