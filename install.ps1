$py  = "C:\Users\moze1\zero\.venv\Scripts\pythonw.exe"
$dir = "C:\Users\moze1\zero"
$a = New-ScheduledTaskAction -Execute $py -Argument "-m zero" -WorkingDirectory $dir
$user = "$env:COMPUTERNAME\$env:USERNAME"   # fully-qualified; bare name fails task-XML validation
$t = New-ScheduledTaskTrigger -AtLogOn -User $user
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
       -StartWhenAvailable -Hidden -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
       -ExecutionTimeLimit ([TimeSpan]::Zero)
$p = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName "StartZero" -Action $a -Trigger $t -Settings $s -Principal $p -Force
Write-Host "StartZero registered. Ensure ANTHROPIC_API_KEY is NOT set so Zero uses the subscription."
