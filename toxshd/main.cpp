#include <stdio.h>

#include <QtCore>
#include "debugoutput.h"

#include "server.h"

int main(int argc, char**argv)
{
    // setenv("QT_MESSAGE_PATTERN", "[%{type}] %{appname} (%{file}:%{line}) T%{threadid} %{function} - %{message} ", 1);
    qInstallMessageHandler(myMessageOutput);
    QCoreApplication a(argc, argv);

    Server s;



    return a.exec();
    return 0;
}
