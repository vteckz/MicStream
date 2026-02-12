package com.micstream

import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.util.Log
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class RemoteTouchSender(
    private val host: String,
    private val port: Int,
    private val connectivityManager: ConnectivityManager?
) {
    companion object {
        const val TAG = "RemoteTouch"
        const val SCREEN_W = 1024
        const val SCREEN_H = 768
        val CMD_DOWN: Byte = 'D'.code.toByte()
        val CMD_MOVE: Byte = 'M'.code.toByte()
        val CMD_UP: Byte = 'U'.code.toByte()
    }

    private var socket: DatagramSocket? = null
    private var addr: InetAddress? = null
    private val executor: ExecutorService = Executors.newSingleThreadExecutor()
    var statusMessage: String = "Not connected"
        private set
    var onStatusChanged: ((String) -> Unit)? = null

    private fun ensureSocket() {
        if (socket != null && addr != null) return

        addr = InetAddress.getByName(host)
        val s = DatagramSocket()

        // Try to bind to WiFi network (needed when AA wireless monopolizes WiFi)
        var wifiBound = false
        try {
            connectivityManager?.let { cm ->
                @Suppress("DEPRECATION")
                for (network in cm.allNetworks) {
                    val caps = cm.getNetworkCapabilities(network)
                    if (caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
                        network.bindSocket(s)
                        wifiBound = true
                        Log.i(TAG, "Bound touch socket to WiFi network")
                        break
                    }
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "WiFi bind failed: ${e.message}")
        }

        socket = s
        val msg = "Touch ready -> $host:$port" + if (wifiBound) " (WiFi)" else " (default route)"
        Log.i(TAG, msg)
        statusMessage = msg
        onStatusChanged?.invoke(msg)
    }

    fun send(cmd: Byte, x: Int, y: Int) {
        executor.submit {
            try {
                ensureSocket()
                val s = socket ?: return@submit
                val a = addr ?: return@submit
                val buf = ByteBuffer.allocate(5).order(ByteOrder.LITTLE_ENDIAN)
                buf.put(cmd)
                buf.putShort(x.toShort())
                buf.putShort(y.toShort())
                val data = buf.array()
                s.send(DatagramPacket(data, data.size, a, port))
            } catch (e: Exception) {
                Log.w(TAG, "Send error: ${e.message}")
                statusMessage = "Error: ${e.message}"
                onStatusChanged?.invoke(statusMessage)
                // Reset so next send retries connection
                try { socket?.close() } catch (_: Exception) {}
                socket = null
                addr = null
            }
        }
    }

    fun tap(x: Int, y: Int) {
        executor.submit {
            try {
                ensureSocket()
                val s = socket ?: return@submit
                val a = addr ?: return@submit

                fun sendPacket(cmd: Byte, px: Int, py: Int) {
                    val buf = ByteBuffer.allocate(5).order(ByteOrder.LITTLE_ENDIAN)
                    buf.put(cmd)
                    buf.putShort(px.toShort())
                    buf.putShort(py.toShort())
                    val data = buf.array()
                    s.send(DatagramPacket(data, data.size, a, port))
                }

                sendPacket(CMD_DOWN, x, y)
                Thread.sleep(50)
                sendPacket(CMD_UP, x, y)
            } catch (e: Exception) {
                Log.w(TAG, "Tap error: ${e.message}")
            }
        }
    }

    fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, steps: Int = 10) {
        executor.submit {
            try {
                ensureSocket()
                val s = socket ?: return@submit
                val a = addr ?: return@submit

                fun sendPacket(cmd: Byte, x: Int, y: Int) {
                    val buf = ByteBuffer.allocate(5).order(ByteOrder.LITTLE_ENDIAN)
                    buf.put(cmd)
                    buf.putShort(x.toShort())
                    buf.putShort(y.toShort())
                    val data = buf.array()
                    s.send(DatagramPacket(data, data.size, a, port))
                }

                sendPacket(CMD_DOWN, x1, y1)
                for (i in 1..steps) {
                    val x = x1 + (x2 - x1) * i / steps
                    val y = y1 + (y2 - y1) * i / steps
                    Thread.sleep(15)
                    sendPacket(CMD_MOVE, x, y)
                }
                Thread.sleep(10)
                sendPacket(CMD_UP, x2, y2)
            } catch (e: Exception) {
                Log.w(TAG, "Swipe error: ${e.message}")
            }
        }
    }

    fun close() {
        try { socket?.close() } catch (_: Exception) {}
        socket = null
        addr = null
        executor.shutdown()
    }
}
