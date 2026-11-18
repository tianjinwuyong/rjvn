
$db = "D:\stations\ate_ng_pool.db"
$py = "python"
$cmd = "$py -c `"import sqlite3; c=sqlite3.connect('$db'); cu=c.cursor(); cu.execute('select count(*) from ng_pool'); print(cu.fetchone()[0]); cu.execute('select sn,station_key,result,test_time from ng_pool order by test_time desc limit 5'); [print(r) for r in cu.fetchall()]`""
$output = Invoke-Expression $cmd
Write-Output $output
