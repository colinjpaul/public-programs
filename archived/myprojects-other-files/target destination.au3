#include <File.au3>
$n = InputBox("Input","Enter the target file path")
$d = InputBox("Input","Enter the destination file path")
FileOpen($n,1)
$p = FileRead("C:\Users\Hi\Desktop\AutoIT\New Source\locker.au3")
FileClose("C:\Users\Hi\Desktop\AutoIT\New Source\locker.au3")
_FileCreate($d)
FileOpen($d,1)
FileWrite($d,$p)
FileClose($d)