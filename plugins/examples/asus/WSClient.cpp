#include "WSClient.h"
#include <iostream>
#include <sstream>

WebSocketClient::WebSocketClient(const std::string& uri, const std::string& json_msg)
    : m_uri(uri), m_json_msg(json_msg), m_message_received(false), m_status_change(false), m_open(false)
{

    m_client.clear_access_channels(websocketpp::log::alevel::all);
    m_client.clear_error_channels(websocketpp::log::alevel::all);

    m_client.init_asio();

    m_client.set_open_handler(websocketpp::lib::bind(&WebSocketClient::on_open, this, websocketpp::lib::placeholders::_1));
    m_client.set_message_handler(websocketpp::lib::bind(&WebSocketClient::on_message, this, websocketpp::lib::placeholders::_1, websocketpp::lib::placeholders::_2));
    m_client.set_close_handler(websocketpp::lib::bind(&WebSocketClient::on_close, this, websocketpp::lib::placeholders::_1));
    m_client.set_fail_handler(websocketpp::lib::bind(&WebSocketClient::on_fail, this, websocketpp::lib::placeholders::_1));
}

void WebSocketClient::start()
{
    websocketpp::lib::error_code ec;

    client::connection_ptr con = m_client.get_connection(m_uri, ec);
    if (ec) {
        return;
    }

    m_client.connect(con);

    m_client_thread.reset(new websocketpp::lib::thread(&client::run, &m_client));
}

bool WebSocketClient::wait_for_status_change(int timeout_seconds)
{
    std::unique_lock<std::mutex> lock(m_mutex);
    return m_cond_var.wait_for(lock, std::chrono::seconds(timeout_seconds), [this] { return m_status_change; });
}

void WebSocketClient::close()
{
    websocketpp::lib::error_code ec;

    if (m_open) {
        m_client.close(m_hdl, websocketpp::close::status::going_away, "", ec);
        if (ec) {
        }
    }

    if (m_client_thread) {
        m_client_thread->join();
    }
}

void WebSocketClient::on_open(websocketpp::connection_hdl hdl)
{
    m_hdl = hdl;

    m_open = true;
    // Send the JSON message
    send_message(m_json_msg);
}

void WebSocketClient::on_fail(websocketpp::connection_hdl hdl)
{
    client::connection_ptr con = m_client.get_con_from_hdl(hdl);

    std::lock_guard<std::mutex> lock(m_mutex);

    m_status_change = true;
    m_cond_var.notify_one();
    
}

void WebSocketClient::on_message(websocketpp::connection_hdl hdl, client::message_ptr msg)
{

    std::lock_guard<std::mutex> lock(m_mutex);
    m_status_change = true;
    m_message_received = true;
    m_cond_var.notify_one();
}

void WebSocketClient::on_close(websocketpp::connection_hdl hdl)
{
}

void WebSocketClient::send_message(const std::string& msg)
{
    websocketpp::lib::error_code ec;

    m_client.send(m_hdl, msg, websocketpp::frame::opcode::text, ec);
}

