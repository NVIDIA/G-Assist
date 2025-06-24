#pragma once

#include <websocketpp/config/asio_no_tls_client.hpp>
#include <websocketpp/client.hpp>
#include <websocketpp/common/thread.hpp>


#include <string>
#include <mutex>
#include <condition_variable>

typedef websocketpp::client<websocketpp::config::asio_client> client;

class WebSocketClient
{
public:
    WebSocketClient(const std::string& uri, const std::string& json_msg);
    void start();
    bool wait_for_status_change(int timeout_seconds);
    void close();
    bool m_message_received;

private:
    void on_open(websocketpp::connection_hdl hdl);
    void on_message(websocketpp::connection_hdl hdl, client::message_ptr msg);
    void on_close(websocketpp::connection_hdl hdl);
    void on_fail(websocketpp::connection_hdl hdl);
    void send_message(const std::string& msg);

    client m_client;
    websocketpp::connection_hdl m_hdl;
    std::string m_uri;
    std::string m_json_msg;
    websocketpp::lib::shared_ptr<websocketpp::lib::thread> m_client_thread;
    std::mutex m_mutex;
    std::condition_variable m_cond_var;
    bool m_status_change;
    bool m_open;
};


