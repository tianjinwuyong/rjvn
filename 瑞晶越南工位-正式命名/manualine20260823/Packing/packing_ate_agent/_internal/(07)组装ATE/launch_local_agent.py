import os
import runpy

os.environ["MES_PRIMARY_URL"] = "http://192.168.6.155:8080"
os.environ["MES_BACKUP_URL"] = "http://192.168.6.122:8080"
os.environ["MES_LOCAL_URL"] = "http://127.0.0.1:8080"
os.environ["STATION_REQUIRE_NG_SYNC"] = "1"
runpy.run_path("assembly_ate_agent.py", run_name="__main__")
