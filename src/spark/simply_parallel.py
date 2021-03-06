"""
Homomorphic encryption implemented by using existing PySEAL. Horizontal scaling. 

Sources: Spark quickstart
https://www.rittmanmead.com/blog/2017/01/getting-started-with-spark-streaming-with-python-and-kafka/
TODO look into pass-by-ref or pass-by-value of the C++ objects and memory. \n
TODO SEAL does everything in-place, \n
TODO what happens when we convert to functional proggramming?
"""
from pyspark.sql import SparkSession
# SparkSession is newer, recommended API over SparkContext
from pyspark import SparkContext
from pyspark.streaming import StreamingContext
from pyspark.streaming.kafka import KafkaUtils
import json
from kafka_consumer import kafka_consumer_gen
from kafka_producer import (producer, send_blob_to_prod)
import seal
from seal import ChooserEvaluator, \
	Ciphertext, \
	Decryptor, \
	Encryptor, \
	EncryptionParameters, \
	Evaluator, \
	IntegerEncoder, \
	FractionalEncoder, \
	KeyGenerator, \
	MemoryPoolHandle, \
	Plaintext, \
	SEALContext, \
	EvaluationKeys, \
	GaloisKeys, \
	PolyCRTBuilder, \
	ChooserEncoder, \
	ChooserEvaluator, \
	ChooserPoly
from timeit import default_timer



def simply_parallel():
	start = default_timer() # TODO extract to test/experiment
	print(do_per_amount(10))
	print("It took "+ str(default_timer() - start))

	# Streaming test
	sc = SparkContext(appName="simply_parallel_HE")
	sc.setLogLevel("WARN")
	ssc = StreamingContext(sc, 2)
	topics = ['eth-old']
	kafka_broker = 'ec2-52-11-165-61.us-west-2.compute.amazonaws.com:9092,\
					ec2-52-40-90-99.us-west-2.compute.amazonaws.com:9092,\
					ec2-34-218-39-83.us-west-2.compute.amazonaws.com:9092'
	groupId = 'spark-streaming'

	directKafkaStream = KafkaUtils.createDirectStream(ssc, topics, {"metadata.broker.list": kafka_broker})
	directKafkaStream.pprint()
	parsed = directKafkaStream.map(lambda x: float(x[1]))
	parsed.pprint()
	result = parsed.map(do_per_amount)
	result.pprint()
	result.foreachRDD(lambda rdd: rdd.foreachPartition(output_set_of_transactions))

	ssc.start()
	ssc.awaitTermination()

	# TODO
	# Source: https://spark.apache.org/docs/2.3.1/streaming-kafka-0-8-integration.html
	offsetRanges = []

	def storeOffsetRanges(rdd):
		global offsetRanges
		offsetRanges = rdd.offsetRanges()
		return rdd

	def printOffsetRanges(rdd):
		for o in offsetRanges:
			print("%s %s %s %s" % (o.topic, o.partition, o.fromOffset, o.untilOffset))

	directKafkaStream \
		.transform(storeOffsetRanges) \
		.foreachRDD(printOffsetRanges)



def output_set_of_transactions(record_list):
    connection = producer()
    for record in record_list:
        send_blob_to_prod(connection, 'eth-decrypted', record)



def do_per_amount(amount, subtract_from=15):
	"""
	Called on every message in the stream
	"""
	print("Transaction amount ", amount)
	parms = EncryptionParameters()
	parms.set_poly_modulus("1x^2048 + 1")
	parms.set_coeff_modulus(seal.coeff_modulus_128(2048))
	parms.set_plain_modulus(1 << 8)
	context = SEALContext(parms)

	# Encode
	encoder = FractionalEncoder(context.plain_modulus(), context.poly_modulus(), 64, 32, 3)

	# To create a fresh pair of keys one can call KeyGenerator::generate() at any time.
	keygen = KeyGenerator(context)
	public_key = keygen.public_key()
	secret_key = keygen.secret_key()

	encryptor = Encryptor(context, public_key)


	plain1 = encoder.encode(amount)
	encoded2 = encoder.encode(subtract_from)

	# Encrypt
	encrypted1 = Ciphertext(parms)
	encryptor.encrypt(plain1, encrypted1)

	# Evaluate
	evaluator = Evaluator(context)
	evaluated = evaluate_subtraction_from_plain(evaluator, encrypted1, encoded2)

	# Decrypt and decode
	decryptor = Decryptor(context, secret_key)
	plain_result = Plaintext()
	decryptor.decrypt(evaluated, plain_result)
	result = encoder.decode(plain_result)

	str_result = "Amount left = " + str(result)
	print(str_result)
	return  str_result


def evaluate_subtraction_from_plain(evaluator, encrypted_single_amount, subtract_from_plaintext):
	"""
	Expects encoded but not encrypted plaintext as arg
	TODO Why do I even need this fn? It provides no generality/composability.
	"""
	evaluator.negate(encrypted_single_amount)
	evaluator.add_plain(encrypted_single_amount, subtract_from_plaintext)

	return encrypted_single_amount



if __name__ == "__main__":
	simply_parallel()
