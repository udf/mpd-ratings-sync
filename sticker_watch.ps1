function New-Watcher {
    param ($folder, $filter)
    $watcher = New-Object IO.FileSystemWatcher $folder, $filter -Property @{ 
        IncludeSubdirectories = $false
        EnableRaisingEvents = $true
    }
    return $watcher
}

function Get-Elapsed {
    param ($timer)
    if ($null -eq $timer) {
        return [double]::PositiveInfinity
    }
    return $timer.elapsed.totalseconds
}

$mpdConfDir = [Environment]::ExpandEnvironmentVariables("%USERPROFILE%\.mpd\")
$ratingsSyncDir = Join-Path -Path $mpdConfDir -ChildPath "ratings_sync"
$dumpRatingsTimer = $null
$loadRatingsTimer = $null
$stickerDBChanged = $false
$syncDBChanged = $false

Register-ObjectEvent (New-Watcher $mpdConfDir "sticker.sql") -EventName "Changed" -MessageData "sticker_db"
Register-ObjectEvent (New-Watcher $mpdConfDir "*.*") -EventName "Changed" -MessageData "sync_db"

while ($true) {
    Start-Sleep -Seconds 1
    Get-Job | Receive-Job

    $events = Get-Event | ForEach-Object {
        Remove-Event $_.EventIdentifier -ErrorAction SilentlyContinue
        return $_.MessageData
    }
    if ($null -ne $events) {
        $stickerDBChanged = $stickerDBChanged -OR $events.contains("sticker_db")
        $syncDBChanged = $syncDBChanged -OR $events.contains("sync_db")
    }

    if ($stickerDBChanged -AND ((Get-Elapsed $dumpRatingsTimer) -ge 10)) {
        $dumpRatingsTimer = [Diagnostics.Stopwatch]::StartNew()
        $stickerDBChanged = $false
        Write-Host "Dumping ratings..."
        Start-Process -Wait -NoNewWindow -FilePath python.exe -WorkingDirectory $ratingsSyncDir -ArgumentList (Join-Path -Path $PSScriptRoot -ChildPath "dump_ratings.py")
    }
    if ($syncDBChanged -AND ((Get-Elapsed $loadRatingsTimer) -ge 10)) {
        $loadRatingsTimer = [Diagnostics.Stopwatch]::StartNew()
        $syncDBChanged = $false
        Write-Host "Loading ratings..."
        Start-Process -Wait -NoNewWindow -FilePath python.exe -WorkingDirectory $ratingsSyncDir -ArgumentList (Join-Path -Path $PSScriptRoot -ChildPath "load_ratings.py")
     }
}
