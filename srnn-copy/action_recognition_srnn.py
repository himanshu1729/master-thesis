import tensorflow as tf
import numpy as np
import sys, random, math
import os, time
import cPickle as pickle
from SRNN import SRNN_model
from SRNN import LSTM_model
import read_data as rd

"""
import action_recognition_srnn as ma
tr,va,te = ma.synthetic_data(4,2,0,5,5)
b = ma.get_random_batch(tr,4,2)
"""

NUM_ACTIVITIES = 12

tf.app.flags.DEFINE_float("learning_rate", 0.0001, "Learning rate.")
tf.app.flags.DEFINE_float("learning_rate_decay_factor", 0.95,
                          "Learning rate decays by this much.")
tf.app.flags.DEFINE_boolean("l2_reg", False, "Adds a L2 regularization term")
tf.app.flags.DEFINE_float("adam_epsilon", 1e-6,
                          "Epsilon used for numerical stability in Adam optimizer.")
tf.app.flags.DEFINE_float("reg_factor", 1.0,
                          "Lambda for l2 regulariation.")
tf.app.flags.DEFINE_float("max_gradient_norm", 5.0,
                          "Clip gradients to this norm.")
tf.app.flags.DEFINE_boolean("clip", False, "whether or not to clip gradients")
tf.app.flags.DEFINE_integer("batch_size", 16,
                            "Batch size to use during training.")
tf.app.flags.DEFINE_integer("num_units", 1024, "Size of each model layer.")
tf.app.flags.DEFINE_integer("num_layers", 3, "Number of layers in the model.")
tf.app.flags.DEFINE_integer("attention_lstm_num_units", 128, "Number units in the attention LSTM.")
tf.app.flags.DEFINE_integer("attention_num_hidden_fc1", 128, "Number neurons in the attention hidden fc layer.")
tf.app.flags.DEFINE_integer("attention_placement", 0, "Where to put the attention")
tf.app.flags.DEFINE_integer("num_activities", NUM_ACTIVITIES, "Number of decoders, i.e. number of context chords")
tf.app.flags.DEFINE_integer("num_frames", 10, "Number of frames in each example.")
tf.app.flags.DEFINE_integer("num_joints", 15, "Number of frames in each example.")
tf.app.flags.DEFINE_integer("num_temp_features", 4, "Number of frames in each example.")
tf.app.flags.DEFINE_integer("num_st_features", 1, "Number of frames in each example.")
tf.app.flags.DEFINE_string("data", "JHMDB", "Data file name")
tf.app.flags.DEFINE_string("data_pickle",None, "optional pickle file containing the data ")
tf.app.flags.DEFINE_boolean("normalized", False, "Normalized raw joint positionsn")
tf.app.flags.DEFINE_boolean("srnn", True, "Whether to build a SRNN model or simple LSTM")
tf.app.flags.DEFINE_boolean("GD", False, "Uses Gradient Descent with adaptive learning rate")
tf.app.flags.DEFINE_string("train_dir", "models", "Training directory.")
tf.app.flags.DEFINE_string("log_dir", None, "Training directory.")
tf.app.flags.DEFINE_string("gpu", "/gpu:0", "GPU to run ")

tf.app.flags.DEFINE_integer("max_train_data_size", 0,
                            "Limit on the size of training data (0: no limit).")
tf.app.flags.DEFINE_integer("max_valid_data_size", 0,
                            "Limit on the size of validation data (0: no limit).")
tf.app.flags.DEFINE_integer("max_test_data_size", 0,
                            "Limit on the size of validation data (0: no limit).")
tf.app.flags.DEFINE_integer("max_epochs", 0,
                            "Maximium number of epochs for trainig.")
tf.app.flags.DEFINE_integer("steps_per_checkpoint",5,
                            "How many training steps to do per checkpoint.")
tf.app.flags.DEFINE_boolean("self_test", False,
                            "Run a self-test if this is set to True.")
tf.app.flags.DEFINE_boolean("test_model", False,
                            "Evaluate an existing model on test data")

FLAGS = tf.app.flags.FLAGS

def extract_features(dir_name='/local/home/msephora/master-thesis/master-thesis/srnn-TF/data/JHMDB/joint_positions',
                     sub_activities=True, data='UTK',num_frames=FLAGS.num_frames, normalized=FLAGS.normalized,cross_subject=False):

    # if not get_train_data ^ get_valid_data ^ get_test_data or get_train_data & get_valid_data & get_test_data:
    #     raise ValueError("Only one of training_data, valid_data and test_data must be True")

    if sub_activities:
        num_activities = 12
    else:
        num_activities = 21

    if data == 'MSR':
        dir_name='/local/home/msephora/master-thesis/master-thesis/srnn-TF/data/MSRAction3D/MSRAction3DSkeleton(20joints)'
        train_data, train_num_video, valid_data, valid_num_video, max, min  = rd.get_pos_imgsMRS(dir_name,subset_joints=False)
        num_activities = 20
        num_joints = 20
    elif data == 'UTK':
        train_data, train_num_video, valid_data, valid_num_video, max, min = rd.get_pos_imgsUTK(subset_joints=False)
        num_activities = 10
        num_joints = 20
    elif data == 'NTU':
        train_data, train_num_video, valid_data, valid_num_video, max, min = rd.get_pos_imgsNTU(cross_subject=cross_subject, subset_joints=True)
        num_activities = 60
        num_joints = 6
    else:
        train_data, train_num_video, valid_data, valid_num_video = rd.get_pos_imgsJHMDB(dir_name, sub_activities=sub_activities, normalized=normalized,subset_joints=False)
        num_joints=15

    # print('max num frames =')
    # print(max)
    # print('min num frames =')
    # print(min)
    if data == 'JHMDB':
        train_dataset = rd.extract_all_features(train_data,train_num_video,num_activities,num_considered_frames=num_frames,num_joints=num_joints, JHMDB=True)
        valid_dataset = rd.extract_all_features(valid_data,valid_num_video,num_activities,num_considered_frames=num_frames,num_joints=num_joints, JHMDB=True)
    else:
        train_dataset = rd.extract_all_features(train_data,train_num_video,num_activities,num_considered_frames=num_frames,num_joints=num_joints)
        valid_dataset = rd.extract_all_features(valid_data,valid_num_video,num_activities,num_considered_frames=num_frames,num_joints=num_joints)

    return train_dataset, valid_dataset

def create_pickle(pickle_name, num_frames, data, cross_subject):
    tr,te= extract_features(num_frames=num_frames,normalized=True, data=data, cross_subject=cross_subject)
    dic={'train':tr,'test':te}
    pickle.dump(dic,open(pickle_name,'wb'))
    return dic

def create_pickle_fromdata(pickle_name, data_name, num_frames, valid_num_video, train_num_video, num_activities):
    tr = pickle.load(open(data_name,'rb'))
    te = pickle.load(open(data_name,'rb'))
    train_dataset = rd.extract_features(tr,train_num_video,num_activities,num_considered_frames=num_frames)
    valid_dataset = rd.extract_features(te,valid_num_video,num_activities,num_considered_frames=num_frames)
    dic={'train':train_dataset,'test':valid_dataset}
    pickle.dump(dic,open(pickle_name,'wb'))

def synthetic_data(train_size, valid_size, test_size,num_frames,num_features):
    temp_features_names = ['face-face','belly-belly','rightArm-rightArm','leftArm-leftArm','rightLeg-rightLeg','leftLeg-leftLeg']
    st_features_names = ['face-leftArm','face-rightArm','face-belly','belly-leftArm','belly-rightArm',
                             'belly-rightLeg','belly-leftLeg','leftArm-rightArm','leftLeg-rightLeg']

    def random_action(size):
        action = np.random.randint(0, NUM_ACTIVITIES, size=size)
        y = np.zeros((size,NUM_ACTIVITIES))
        for idx in zip(range(size),action) :
            y[idx]=1
        return y
    train_data = np.array({})
    temp_features = {}
    for name in temp_features_names:
        temp_features[name] = np.random.rand(train_size,num_frames,num_features)
    st_features = {}
    for name in st_features_names:
        st_features[name] = np.random.rand(train_size,num_frames,num_features)
    train_data_sample = np.array([{},{},[]])
    train_data_sample[0] = temp_features
    train_data_sample[1] = st_features
    train_data_sample[2] = random_action(train_size)

    train_data = np.append(train_data,train_data_sample)
    train_data = np.delete(train_data,0)

    valid_data = np.array({})
    temp_features = {}
    for name in temp_features_names:
        temp_features[name] = np.random.rand(valid_size,num_frames,num_features)
    st_features = {}
    for name in st_features_names:
        st_features[name] = np.random.rand(valid_size,num_frames,num_features)
    valid_data_sample = np.array([{},{},[]])
    valid_data_sample[0] = temp_features
    valid_data_sample[1] = st_features
    valid_data_sample[2] = random_action(valid_size)

    valid_data = np.append(valid_data,valid_data_sample)
    valid_data = np.delete(valid_data,0)

    test_data = np.array({})
    temp_features = {}
    for name in temp_features_names:
        temp_features[name] = np.random.rand(test_size,num_frames,num_features)
    st_features = {}
    for name in st_features_names:
        st_features[name] = np.random.rand(test_size,num_frames,num_features)
    test_data_sample = np.array([{},{},[]])
    test_data_sample[0] = temp_features
    test_data_sample[1] = st_features
    test_data_sample[2] = random_action(test_size)

    test_data = np.append(test_data,test_data_sample)
    test_data = np.delete(test_data,0)

    return train_data, valid_data, test_data


def get_random_batch(data, batch_size):
    data_size = len(data[2])
    batch = np.array({})
    idxs = random.sample(xrange(0,data_size-1),batch_size)
    info_idxs = np.array(data[3].keys())[idxs]
    batch_dic = np.array([{},{},[]])
    for i in xrange(len(data)-1):
        dic = data[i]
        if i<2:
            batch_sub_dic = {}
            for key in dic:
                batch_sub_dic[key]=dic[key][idxs]
            batch_dic[i] = batch_sub_dic
        else:
            batch_dic[i] = dic[idxs]
    batch = np.append(batch,batch_dic)
    batch = np.delete(batch,0)
    batch_info = {}
    for key in info_idxs:
        batch_info[key]=data[3][key]
    return batch, batch_info

def get_random_batch_alldata(data, batch_size):
    data_size = len(data[2])
    batch = np.array({})
    idxs = random.sample(xrange(0,data_size-1),batch_size)
    info_idxs = np.array(data[2].keys())[idxs]
    batch_dic = np.array([{},[]])
    for i in xrange(len(data)-1):
        dic = data[i]
        if i<1:
            batch_sub_dic = {}
            for key in dic:
                batch_sub_dic[key]=dic[key][idxs]
            batch_dic[i] = batch_sub_dic
        else:
            batch_dic[i] = dic[idxs]
    batch = np.append(batch,batch_dic)
    batch = np.delete(batch,0)
    batch_info = {}
    for key in info_idxs:
        batch_info[key]=data[2][key]
    return batch, batch_info

def split_data(data, validation_proportion):
    data_size = len(data[2])
    random.seed(14)
    valid_split_size = int(round(data_size*validation_proportion))
    valid_split = np.array({})
    train_split = np.array({})
    valid_idxs = random.sample(xrange(0,data_size),valid_split_size)
    train_idxs = range(data_size)
    for a in valid_idxs:
        train_idxs.remove(a)

    valid_dic = np.array([{},{},[],{}])
    train_dic = np.array([{},{},[],{}])

    for i in xrange(len(data)-1):
        dic = data[i]
        if i<2:
            valid_sub_dic = {}
            train_sub_dic = {}
            for key in dic:
                valid_sub_dic[key]=dic[key][valid_idxs]
                train_sub_dic[key]=dic[key][train_idxs]
            valid_dic[i] = valid_sub_dic
            train_dic[i] = train_sub_dic
        else:
            valid_dic[i] = dic[valid_idxs]
            train_dic[i] = dic[train_idxs]

    valid_info = {}
    train_info = {}
    for key in valid_idxs:
        valid_info[key]=data[3][key]
    for key in train_idxs:
        train_info[key]=data[3][key]

    valid_dic[3] = valid_info
    train_dic[3] = train_info

    valid_split = np.append(valid_split,valid_dic)
    train_split = np.append(train_split,train_dic)
    valid_split = np.delete(valid_split,0)
    train_split = np.delete(train_split,0)
    return valid_split,train_split

def split_all_data(data, validation_proportion):
    data_size = len(data[2])
    random.seed(14)
    valid_split_size = int(round(data_size*validation_proportion))
    valid_split = np.array({})
    train_split = np.array({})
    valid_idxs = random.sample(xrange(0,data_size),valid_split_size)
    train_idxs = range(data_size)
    for a in valid_idxs:
        train_idxs.remove(a)

    valid_dic = np.array([{},[],{}])
    train_dic = np.array([{},[],{}])

    for i in xrange(len(data)-1):
        dic = data[i]
        if i<1:
            valid_sub_dic = {}
            train_sub_dic = {}
            for key in dic:
                valid_sub_dic[key]=dic[key][valid_idxs]
                train_sub_dic[key]=dic[key][train_idxs]
            valid_dic[i] = valid_sub_dic
            train_dic[i] = train_sub_dic
        else:
            valid_dic[i] = dic[valid_idxs]
            train_dic[i] = dic[train_idxs]

    valid_info = {}
    train_info = {}
    for key in valid_idxs:
        valid_info[key]=data[2][key]
    for key in train_idxs:
        train_info[key]=data[2][key]

    valid_dic[2] = valid_info
    train_dic[2] = train_info

    valid_split = np.append(valid_split,valid_dic)
    train_split = np.append(train_split,train_dic)
    valid_split = np.delete(valid_split,0)
    train_split = np.delete(train_split,0)
    return valid_split,train_split

def create_SRNN_model(session, forward_only,log_dir, result_file=None, same_param=False):

    model = SRNN_model(FLAGS.num_activities, FLAGS.num_frames, FLAGS.num_temp_features, FLAGS.num_st_features, FLAGS.num_units, FLAGS.max_gradient_norm, FLAGS.learning_rate,
                       FLAGS.learning_rate_decay_factor, FLAGS.adam_epsilon, FLAGS.GD, forward_only=forward_only, l2_regularization=FLAGS.l2_reg, weight_decay=FLAGS.reg_factor, log_dir=log_dir)

    if not same_param:
        checkpoint = tf.train.get_checkpoint_state(FLAGS.train_dir)
        if checkpoint and tf.gfile.Exists(checkpoint.model_checkpoint_path):
            if result_file is not None:
                result_file.write("Continue training existing model! ")
            print("Reading model parameters from %s" % checkpoint.model_checkpoint_path)
            model.saver.restore(session, checkpoint.model_checkpoint_path)
            session.run(model.learning_rate.assign(float(FLAGS.learning_rate)))
            model.adam_epsilon = FLAGS.adam_epsilon
        else:
            print("Created model with fresh parameters.")
            if FLAGS.log_dir is not None:
                model.train_writer.add_graph(session.graph)
            #session.run(tf.global_variables_initializer())
            session.run(tf.initialize_all_variables()) 
    return model

def create_LSTM_model(session, forward_only,log_dir, result_file=None,same_param=False):

    model = LSTM_model(FLAGS.num_activities, FLAGS.num_joints,FLAGS.num_frames, FLAGS.num_temp_features, FLAGS.num_units, FLAGS.num_layers, FLAGS.attention_lstm_num_units,
                       FLAGS.attention_num_hidden_fc1, FLAGS.attention_placement, FLAGS.max_gradient_norm, FLAGS.learning_rate, FLAGS.learning_rate_decay_factor,
                       FLAGS.adam_epsilon, FLAGS.GD, forward_only=forward_only, l2_regularization=FLAGS.l2_reg, weight_decay=FLAGS.reg_factor, log_dir=log_dir)

    if not same_param:
        checkpoint = tf.train.get_checkpoint_state(FLAGS.train_dir)
        if checkpoint and tf.gfile.Exists(checkpoint.model_checkpoint_path):
            if result_file is not None:
                result_file.write("Continue training existing model! ")
            print("Reading model parameters from %s" % checkpoint.model_checkpoint_path)
            model.saver.restore(session, checkpoint.model_checkpoint_path)
            session.run(model.learning_rate.assign(float(FLAGS.learning_rate)))
            model.adam_epsilon = FLAGS.adam_epsilon
        else:
            print("Created model with fresh parameters.")
            if FLAGS.log_dir is not None:
                model.train_writer.add_graph(session.graph)
            #session.run(tf.global_variables_initializer())
            session.run(tf.initialize_all_variables())
    return model

def main(_):
    if not os.path.exists(FLAGS.train_dir):
        os.makedirs(FLAGS.train_dir)
    # log_dir = str(FLAGS.train_dir +'/logs')
    # if not os.path.exists(log_dir):
    #     os.makedirs(log_dir)
    result_file = open(FLAGS.train_dir + "/results.txt", 'a+')

    if FLAGS.data_pickle is None:
        if FLAGS.data == "MSR":
            if FLAGS.num_frames == 10:
                data = pickle.load( open( "dataMSR.pickle", "rb" ) )
                print("Training on MSR Action 3D data using 10 frames")
                result_file.write("Training on MSR Action 3D data using 10 frames ")
            elif FLAGS.num_frames == 30:
                data = pickle.load( open( "dataMSR30f.pkl", "rb" ) )
                print("Training on MSR Action 3D data using 30 frames")
                result_file.write("Training on MSR Action 3D data using 30 frames")
            elif FLAGS.num_frames == 40:
                print("Training on MSR Action 3D data using 40 frames")
                result_file.write("Training on MSR Action 3D data using 40 frames")
        else:
            if FLAGS.num_frames == 10:
                data = pickle.load( open( "norm3_10frames.pkl", "rb" ) )
                print("Training on JHMDB data using 10 frames ")
                result_file.write("Training on JHMDB data using 10 frames")
            elif FLAGS.num_frames == 20:
                data = pickle.load( open( "split1_20f", "rb" ) )
                print("Training on JHMDB data using 20 frames ")
                result_file.write("Training on JHMDB data using 20 frames")
            elif FLAGS.num_frames == 30:
                data = pickle.load( open( "split1_30f", "rb" ) )
                print("Training on JHMDB data using 30 frames ")
                result_file.write("Training on JHMDB data using 30 frames")
            elif FLAGS.num_frames == 40:
                data = pickle.load( open( "split1_40f", "rb" ) )
                print("Training on JHMDB data using 40 frames ")
                result_file.write("Training on JHMDB data using 40 frames")
    else:
        data = pickle.load( open( FLAGS.data_pickle, "rb" ) )


    all_train_data = data['train']

    if FLAGS.srnn:
        valid_data, train_data= split_data(all_train_data, 0.2)
    else:
        valid_data, train_data= split_all_data(all_train_data, 0.2)

    test_data = data['test']
    print("Sizes:  train: %d    valid:  %d    test: %d" % (len(train_data[2]), len(valid_data[2]), len(test_data[2])))
    train_data_size = len(train_data[2])
    steps_per_epoch = int(train_data_size/FLAGS.batch_size)



    with tf.device(FLAGS.gpu):
        config = tf.ConfigProto(allow_soft_placement = True)
        with tf.Session(config = config) as sess:
            with tf.name_scope("Train"):
                result_file.write("Creating SRNN model \n")
                #initializer = tf.random_uniform_initializer(-0.05,0.05)
                with tf.variable_scope("Model", reuse=None) : #, initializer=initializer):
                    print("Creating SRNN model ")
                    print("with %d units and %d bach-size." % (FLAGS.num_units, FLAGS.batch_size))
                    if not FLAGS.GD:
                        print("with Adam Optimizer")
                    result_file.write("with %d units and %d bach-size." % (FLAGS.num_units, FLAGS.batch_size))

                    if FLAGS.srnn:
                        model = create_SRNN_model(sess,False,FLAGS.log_dir,result_file)
                    else:
                        model = create_LSTM_model(sess, False, FLAGS.log_dir, result_file)
                    

                    if FLAGS.max_train_data_size:
                        train_data = train_data[:FLAGS.max_train_data_size]
                    if FLAGS.max_valid_data_size:
                        test_data = test_data[:FLAGS.max_valid_data_size]
                    # if FLAGS.max_test_data_size:
                    #     test_data = test_data[:FLAGS.max_test_data_size]

                    checkpoint_path = FLAGS.train_dir + "/srnn_model.ckpt"

                    step_time, ckpt_loss,epoch_loss = 0.0, 0.0,0.0
                    current_step = 0
                    current_epoch = divmod(model.global_step.eval(),steps_per_epoch)[0]

                    result_file.write(
                    " %d batch size %d number of steps to complete one epoch \n" % (FLAGS.batch_size, steps_per_epoch))
                    print(
                    " %d batch size %d number of steps to complete one epoch \n" % (FLAGS.batch_size, steps_per_epoch))
                    previous_losses,previous_train_loss, previous_eval_loss = [],[],[]
                    best_train_loss, best_val_loss = np.inf, np.inf
                    best_val_epoch = current_epoch
                    strikes = 0
                    train_batch_id = 1
                    step_output,step_loss,step_logits = None, 0.0, None
                    while int(model.global_step.eval()/steps_per_epoch) < FLAGS.max_epochs:
                        start_time = time.time()
                        if FLAGS.srnn:
                            batch,_ = get_random_batch(train_data,FLAGS.batch_size)
                        else:
                            batch,_ = get_random_batch_alldata(train_data,FLAGS.batch_size)
                        temp_input_batch = batch[0]
                        st_input_batch = batch[1]
                        target_batch = batch[-1]
                        if math.isnan(step_loss):
                            print(step_output)
                            print(step_logits)
                        if current_step % FLAGS.steps_per_checkpoint == 0 and FLAGS.log_dir is not None:
                            if FLAGS.srnn:
                                _ , step_loss, _, summary = model.step_with_summary(sess,temp_input_batch, st_input_batch, target_batch, False,FLAGS.batch_size)
                                model.train_writer.add_summary(summary,model.global_step.eval())
                            else:
                                step_grad_norm , step_loss, _, step_output, step_logits = model.step(sess,temp_input_batch, target_batch , False, FLAGS.batch_size)
                                #_ , step_loss, _, summary = model.step_with_summary(sess,temp_input_batch, target_batch, False,FLAGS.batch_size)
                                #model.train_writer.add_summary(summary,model.global_step.eval())
                        else:
                            if FLAGS.srnn:
                                _ , step_loss, _ = model.step(sess,temp_input_batch, st_input_batch, target_batch, False, FLAGS.batch_size)
                            else:
                                #print(np.array([np.where(T == 1) for T in target_batch]).flatten() )
                                step_grad_norm , step_loss, _, step_output, step_logits = model.step(sess,temp_input_batch, target_batch , False, FLAGS.batch_size)


                        step_time += (time.time() - start_time) / FLAGS.steps_per_checkpoint
                        ckpt_loss += step_loss / FLAGS.steps_per_checkpoint
                        epoch_loss += step_loss/steps_per_epoch

                        current_step += 1
                        train_batch_id += 1
                        if current_step % FLAGS.steps_per_checkpoint == 0:
                            # Print statiistics for the previous epoch
                            print ("batch no %d epoch %d" % (train_batch_id,current_epoch))
                            print ("global step %d learning rate %.4f step-time %.3f loss %.4f "
                                   % (model.global_step.eval(), model.learning_rate.eval(),
                                      step_time, ckpt_loss))
                            result_file.write("global step %d learning rate %.4f step-time %.3f loss %.4f \n"
                                   % (model.global_step.eval(), model.learning_rate.eval(),
                                      step_time, ckpt_loss))
                            #print(step_targets)
                            # Decrease learning rate if no improvement was seen over last 3 times.
                            if FLAGS.GD:
                                if len(previous_losses) > 2 and ckpt_loss > max(previous_losses[-3:]):
                                    sess.run(model.learning_rate_decay_op)
                            previous_losses.append(ckpt_loss)
                            step_time, ckpt_loss = 0.0, 0.0

                        if model.global_step.eval() % steps_per_epoch == 0:
                            print ("epoch %d finished" % (current_epoch))
                            result_file.write("epoch  %d finished \n" % (current_epoch))

                            previous_train_loss.append(epoch_loss)
                            print("  avg train batch:  loss %.4f " % (epoch_loss))
                            result_file.write("  avg train batch:  loss %.4f  \n" % (epoch_loss))
                            epoch_loss = 0.0

                            valid_loss, valid_accuracy = model.big_step(sess,valid_data,valid_data[2]) # if the valid set is too large, use model.steps() instead
                            #valid_loss, valid_accuracy = model.big_step(sess,test_data,len(test_data[2]))
                            print("  eval:  loss %.4f " % (valid_loss))
                            result_file.write("  eval:  loss %.4f  \n" % (valid_loss))
                            previous_eval_loss.append(valid_loss)



                            # Stopping criterion
                            improve_valid = previous_eval_loss[-1] < best_val_loss
                            improve_train = previous_train_loss[-1] < best_train_loss

                            if improve_valid:
                                strikes = 0
                                best_val_loss = previous_eval_loss[-1]
                                best_val_epoch = current_epoch
                                # Save checkpoint.
                                model.saver.save(sess, checkpoint_path, global_step=model.global_step)
                            else:
                                strikes += 1
                                print('STRIKE! %d', (strikes))
                            if improve_train:
                                best_train_loss = previous_train_loss[-1]
                            if strikes > 5:
                                break
                            sys.stdout.flush()
                            train_batch_id =1
                            current_epoch +=1
                    if FLAGS.log_dir is not None:
                        model.train_writer.close()

                    if FLAGS.max_epochs > 0: #ugly hack, fix this!
                        checkpoint = tf.train.get_checkpoint_state(FLAGS.train_dir)
                        model.saver.restore(sess, checkpoint.model_checkpoint_path)

                    print("Training finished!...")
                    print("Best validation loss at epoch %d" % best_val_epoch)
                    result_file.write("Best validation loss at epoch  %d" % best_val_epoch)

                    #test_loss, test_error = model.steps(sess,train_data)
                    #print("  total train  loss %.4f, total train loss %.4f " % (test_loss, test_error))
                    #result_file.write("  total train  loss %.4f, total train loss %.4f " % (test_loss, test_error))

                    #test_loss, test_error = model.steps(sess,test_data, 100)
                    test_loss, test_error = model.big_step(sess,test_data,len(test_data[2]))
                    print("  total test  loss %.4f, total error loss %.4f " % (test_loss, test_error))
                    result_file.write("  total test  loss %.4f, total error loss %.4f " % (test_loss, test_error))

                    # print("random batch")
                    # batch = get_random_batch(train_data,FLAGS.batch_size)
                    # temp_input_batch = batch[0]
                    # st_input_batch = batch[1]
                    # target_batch = batch[-1]
                    # _, batch_cost, batch_output = model.step(sess,temp_input_batch, st_input_batch, target_batch, True)
                    #
                    # print(batch_output)
                    # print(target_batch)

                    # with tf.variable_scope("Model", reuse=True, initializer=initializer):
                    #     model_valid = create_SRNN_model(sess,True,result_file,same_param=True)
                    #     test_loss = model_valid.steps(sess,train_data)
                    #
                    #     print("  total train loss on fresh model   %.4f " % (test_loss))


if __name__ == '__main__':
	tf.app.run()
