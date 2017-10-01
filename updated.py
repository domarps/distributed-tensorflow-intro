import tensorflow as tf
from tensorflow.contrib import slim
from tensorflow.examples.tutorials.mnist import input_data


BATCH_SIZE = 50
TRAINING_STEPS = 5000
PRINT_EVERY = 100
LOG_DIR = "/tmp/log"


parameter_servers = ["localhost:2222"]
workers = ["localhost:2223",
           "localhost:2224",
           "localhost:2225"]

cluster = tf.train.ClusterSpec({"ps": parameter_servers, "worker": workers})


tf.app.flags.DEFINE_string("job_name", "", "'ps' / 'worker'")
tf.app.flags.DEFINE_integer("task_index", 0, "Index of task")
FLAGS = tf.app.flags.FLAGS


server = tf.train.Server(cluster,
                         job_name=FLAGS.job_name,
                         task_index=FLAGS.task_index)

mnist = input_data.read_data_sets('MNIST_data', one_hot=True)


def net(x):
    x_image = tf.reshape(x, [-1, 28, 28, 1])
    net = slim.layers.conv2d(x_image, 32, [5, 5], scope='conv1')
    net = slim.layers.max_pool2d(net, [2, 2], scope='pool1')
    net = slim.layers.conv2d(net, 64, [5, 5], scope='conv2')
    net = slim.layers.max_pool2d(net, [2, 2], scope='pool2')
    net = slim.layers.flatten(net, scope='flatten')
    net = slim.layers.fully_connected(net, 500, scope='fully_connected')
    net = slim.layers.fully_connected(net, 10, activation_fn=None,
                                      scope='pred')
    return net


if FLAGS.job_name == "ps":
    server.join()

elif FLAGS.job_name == "worker":

    with tf.device(tf.train.replica_device_setter(
            worker_device="/job:worker/task:%d" % FLAGS.task_index,
            cluster=cluster)):

        global_step = tf.get_variable('global_step', [],
                                      initializer=tf.constant_initializer(0),
                                      trainable=False)

        x = tf.placeholder(tf.float32, shape=[None, 784], name="x-input")
        y_ = tf.placeholder(tf.float32, shape=[None, 10], name="y-input")
        y = net(x)

        cross_entropy = tf.reduce_mean(
                tf.nn.softmax_cross_entropy_with_logits(logits=y, labels=y_))
        train_step = tf.train.AdamOptimizer(1e-4)\
                .minimize(cross_entropy, global_step=global_step)

        correct_prediction = tf.equal(tf.argmax(y, 1), tf.argmax(y_, 1))
        accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

        init_op = tf.global_variables_initializer()



    # The StopAtStepHook handles stopping after running given steps.
    hooks=[tf.train.StopAtStepHook(last_step=TRAINING_STEPS)]

    # The MonitoredTrainingSession takes care of session initialization,
    # restoring from a checkpoint, saving to a checkpoint, and closing when done
    # or an error occurs.
    with tf.train.MonitoredTrainingSession(master=server.target,
                                           is_chief=(FLAGS.task_index == 0),
                                           checkpoint_dir=LOG_DIR,
                                           hooks=hooks) as mon_sess:
      step = 0
      while not mon_sess.should_stop():
        # Run a training step asynchronously.

          batch_x, batch_y = mnist.train.next_batch(BATCH_SIZE)

          _, acc, step = mon_sess.run([train_step, accuracy, global_step],
                                  {x: batch_x, y_: batch_y})

          if step % PRINT_EVERY == 0:
              print("Worker : {}, Step: {}, Accuracy (batch): {}".\
                  format(FLAGS.task_index, step, acc))

      test_acc = mon_sess.run(accuracy, {x: mnist.test.images, y_: mnist.test.labels})
      print("Test-Accuracy: {}".format(test_acc))


'''
  I. To run, in four terminals:

python distribute.py --job_name="ps" --task_index=0
python distribute.py --job_name="worker" --task_index=0
python distribute.py --job_name="worker" --task_index=1
python distribute.py --job_name="worker" --task_index=2

  II. Otherwise:

import subprocess
subprocess.Popen('python distribute.py --job_name="ps" --task_index=0', 
                 shell=True)
subprocess.Popen('python distribute.py --job_name="worker" --task_index=0', 
                 shell=True)
subprocess.Popen('python distribute.py --job_name="worker" --task_index=1', 
                 shell=True)
subprocess.Popen('python distribute.py --job_name="worker" --task_index=2', 
                 shell=True)
'''
