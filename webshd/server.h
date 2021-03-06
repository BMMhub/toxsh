#ifndef _SERVER_H_
#define _SERVER_H_

#include <QtCore>

class CmdRunner;
class CmdProvider;
class CmdResponser;

class Server : public QObject
{
    Q_OBJECT;
public:
    Server();
    virtual ~Server();

    bool init();

public slots:
    void onStdoutReady(QString out);
    void onStderrReady(QString out);

signals:
    void newCommand(QJsonObject jcmd);

private:
    CmdRunner *m_runner = NULL;
    CmdProvider *m_provider = NULL;
    CmdResponser *m_responser = NULL;
};

#endif /* _SERVER_H_ */
