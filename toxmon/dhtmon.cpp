
// #include <network/GeoIpDatabase.h>
#include <network/GeoIpResolver.h>
#include <network/GeoIpRecord.h>

//
#include <network/NetViewer.h>

#include "dummy.h"

#include "dhtproc.h"

#include "ui_dhtmon.h"
#include "dhtmon.h"


DhtMon::DhtMon()
    : QMainWindow()
    , m_win(new Ui::DhtMon)
{
    m_win->setupUi(this);

    QObject::connect(m_win->pushButton, &QPushButton::clicked, this, &DhtMon::onStart);
    QObject::connect(m_win->pushButton_2, &QPushButton::clicked, this, &DhtMon::onStop);

    // NetViewer *nv = new NetViewer;
    m_nodes_model = new QStringListModel;
    m_win->listView->setModel(m_nodes_model);

    QObject::connect(m_win->listView, &QListView::clicked, this, &DhtMon::onNodeClicked);

    cross_test();

    // NetViewer *nv = new NetViewer;
    // nv->show();
    TorMapImageView *miv = new TorMapImageView;
    // miv->show();
    m_win->gridLayout->addWidget(miv); // no scroll now
    // m_win->scrollArea->setWidget(miv); 
}

DhtMon::~DhtMon()
{
}

void DhtMon::onStart()
{
    m_proc = new DhtProc;
    QObject::connect(m_proc, &DhtProc::pubkeyDone, this, &DhtMon::onPubkeyDone);
    QObject::connect(m_proc, &DhtProc::connected, this, &DhtMon::onConnected);
    QObject::connect(m_proc, &DhtProc::dhtSizeChanged, this, &DhtMon::onDhtSizeChanged);
    QObject::connect(m_proc, &DhtProc::dhtNodesChanged, this, &DhtMon::onDhtNodesChanged);
    QObject::connect(m_proc, &DhtProc::closeNodes, this, &DhtMon::onCloseNodesArrived);

    m_proc->start();
}

void DhtMon::onStop()
{
    
}

void DhtMon::onNodeClicked(const QModelIndex &idx)
{
    QVariant data = m_nodes_model->data(idx, Qt::DisplayRole);
    qDebug()<<idx<<data;
    QString addr = data.toString();
    QString host = addr.split(':').at(0);

    GeoIpResolver *ipres = new GeoIpResolver;
    ipres->setUseLocalDatabase(true);
    QString dbpath = "/usr/share/GeoIP/GeoIP.dat";
    bool bret = ipres->setLocalDatabase(dbpath);

    GeoIpRecord iprec = ipres->resolve(QHostAddress(host));
    qDebug()<<bret<<iprec.isValid();
    delete ipres;

    QString geo_desc = QString("host:%1\n"
                               "city: %2\n"
                               "country: %3\n"
                               "region: %4\n")
        .arg(host).arg(iprec.city()).arg(iprec.country()).arg(iprec.region());

    qDebug()<<geo_desc;

    m_win->plainTextEdit_2->setPlainText(geo_desc);
}

////////////
void DhtMon::onPubkeyDone(QByteArray pubkey)
{
    m_win->lineEdit->setText(QString(pubkey));
}

void DhtMon::onConnected(int conn)
{
    m_win->lineEdit_2->setText(QString("%1").arg(conn));
}

void DhtMon::onDhtSizeChanged(int size)
{
    m_win->lineEdit_3->setText(QString("%1").arg(size));
}

void DhtMon::onDhtNodesChanged(int friendCount, int clientCount, int ping_array_size, int harden_ping_array_size)
{
    m_win->lineEdit_6->setText(QString("%1/%2").arg(friendCount).arg(MAX_FRIEND_CLIENTS * LCLIENT_LIST));
    m_win->lineEdit_7->setText(QString("%1/%2").arg(clientCount).arg(LCLIENT_LIST));
    m_win->lineEdit_8->setText(QString("%1/%2/%3").arg(ping_array_size).arg(harden_ping_array_size)
                               .arg(DHT_PING_ARRAY_SIZE));
}

void DhtMon::onCloseNodesArrived(const QStringList &nodes)
{
    QStringList new_nodes;

    foreach (QString node, nodes) {
        if (m_nodes.contains(node)) continue;
        new_nodes << node;
    }
    m_nodes = nodes;

    // m_nodes_model->setStringList(nodes);
    foreach (QString node, new_nodes) {
        m_nodes_model->insertRows(0, 1);
        m_nodes_model->setData(m_nodes_model->index(0, 0), node, Qt::DisplayRole);
    }
}

