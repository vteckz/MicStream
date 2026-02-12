package com.micstream

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Binder
import android.os.IBinder
import android.util.Log
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

class MicStreamService : Service() {

    companion object {
        const val TAG = "MicStream"
        const val CHANNEL_ID = "mic_stream_channel"
        const val NOTIFICATION_ID = 1
        const val SAMPLE_RATE = 16000
        const val EXTRA_HOST = "host"
        const val EXTRA_PORT = "port"
    }

    interface StatusListener {
        fun onStatusChanged(connected: Boolean, message: String)
    }

    private val binder = LocalBinder()
    var statusListener: StatusListener? = null
    var isStreaming = false
        private set

    private var streamThread: Thread? = null
    private var audioRecord: AudioRecord? = null

    inner class LocalBinder : Binder() {
        fun getService(): MicStreamService = this@MicStreamService
    }

    override fun onBind(intent: Intent?): IBinder = binder

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val host = intent?.getStringExtra(EXTRA_HOST) ?: "192.168.254.1"
        val port = intent?.getIntExtra(EXTRA_PORT, 8000) ?: 8000

        startForeground(NOTIFICATION_ID, buildNotification("Starting..."))

        if (streamThread == null) {
            isStreaming = true
            startStreamThread(host, port)
        }

        return START_STICKY
    }

    override fun onDestroy() {
        stopStreaming()
        super.onDestroy()
    }

    private fun startStreamThread(host: String, port: Int) {
        streamThread = Thread {
            val bufferSize = AudioRecord.getMinBufferSize(
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT
            ).coerceAtLeast(3200)

            var udpSocket: DatagramSocket? = null

            try {
                audioRecord = AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    bufferSize
                )

                if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                    updateStatus(false, "Failed to init mic")
                    return@Thread
                }

                val addr = InetAddress.getByName(host)

                // Try to bind UDP socket to WiFi network
                udpSocket = DatagramSocket()
                try {
                    val cm = getSystemService(ConnectivityManager::class.java)
                    for (network in cm.allNetworks) {
                        val caps = cm.getNetworkCapabilities(network)
                        if (caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
                            network.bindSocket(udpSocket)
                            Log.i(TAG, "Bound UDP socket to WiFi network")
                            break
                        }
                    }
                } catch (e: Exception) {
                    Log.w(TAG, "Could not bind to WiFi: ${e.message}")
                }

                updateNotification("Streaming to $host:$port (UDP)")
                updateStatus(true, "Streaming to $host:$port")
                Log.i(TAG, "Streaming mic via UDP to $host:$port")

                audioRecord!!.startRecording()

                val buffer = ByteArray(1600) // 50ms chunks (16000 * 2 bytes * 0.05s)
                var packetCount = 0L

                while (isStreaming && !Thread.interrupted()) {
                    val read = audioRecord!!.read(buffer, 0, buffer.size)
                    if (read > 0) {
                        val packet = DatagramPacket(buffer, read, addr, port)
                        udpSocket.send(packet)
                        packetCount++
                        if (packetCount % 200 == 0L) { // Update every 10 seconds
                            updateStatus(true, "Streaming ($packetCount packets sent)")
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error: ${e.message}", e)
                updateStatus(false, "Error: ${e.message?.take(50)}")
            } finally {
                try { audioRecord?.stop() } catch (_: Exception) {}
                try { audioRecord?.release() } catch (_: Exception) {}
                try { udpSocket?.close() } catch (_: Exception) {}
                audioRecord = null
            }
        }.also { it.start() }
    }

    private fun stopStreaming() {
        isStreaming = false
        streamThread?.interrupt()
        streamThread?.join(3000)
        streamThread = null
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Mic Stream",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Microphone streaming to Android Auto head unit"
        }
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(channel)
    }

    private fun buildNotification(text: String): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )
        return Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("MicStream")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(text: String) {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, buildNotification(text))
    }

    private fun updateStatus(connected: Boolean, message: String) {
        android.os.Handler(mainLooper).post {
            statusListener?.onStatusChanged(connected, message)
        }
    }
}
