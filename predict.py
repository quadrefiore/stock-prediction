import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
import requests
import io


def differentiate(data, order=1):
    '''
    Diffenrentiates data to make it stationnary:
     - Order 1 : X(n) <- X(n) - X(n-1)
     - Order 2 : X(n) <- X(n) - 2 X(n-1) - X(n-2)
     - ‘return-price’ : X(n) <- (X(n) - X(n-1)) / X(n-1)
    '''
    data_diff = data.copy()
    if order==1:
        data_diff['Close'] = data['Close'].diff()
        data_diff.drop(data_diff.index[0], inplace=True)
    elif order=='return-price':
        data_diff['Close'] = data['Close'].diff() / data_diff['Close'].shift(periods=1)
        data_diff.drop(data_diff.index[0], inplace=True)
    else:
        data_diff['Close'] = data['Close'].diff()
        data_diff.drop(data_diff.index[0], inplace=True)
        data_diff = differentiate(data_diff, order-1)

    return data_diff


def get_alpha_url(symbol, api_key, interval='5min'):
    return 'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol='+symbol+'&interval='+interval+'&apikey='+api_key+'&datatype=csv&outputsize=full'


def prepare_data(symbol, columns=['timestamp', 'close'], distant=False, api_key=None):
    '''
    If distant=False, searches for the csv file corresponding to the company.
    If distant=True, fetches data from the alphavantage api (provide an api key).

    Columns is a list that contains the dates column name and the values column name
    Convert the date column to datetime and sort data from
    the CSV file by date by ascending order.
    The CSV must contain a date column (YYYY-MM-DD)
    '''
    if distant==True and api_key is not None:
        urlData = requests.get(get_alpha_url(symbol, api_key)).content
        if '"Note": "Thank you for using Alpha Vantage!' in str(urlData):
            raise RuntimeError('API limit reached')

        df = pd.read_csv(io.StringIO(urlData.decode('utf-8')))
    else:
        df = pd.read_csv(symbol+'.csv')

    df[columns[0]] = pd.to_datetime(df[columns[0]], format='%Y-%m-%d')
    df.index = df[columns[0]]
    data = df.sort_index(ascending=True, axis=0)

    new_data = pd.DataFrame(index=range(0,len(df)),columns=['Date', 'Close'])
    new_data['Date'] = data[columns[0]].values
    new_data['Close'] = data[columns[1]].values

    return new_data


def inv_differenciate(predictions, diff_order, last_value=None):
    """
    Operates the inverse operation of differenciation.
    last_value is required when the order is > 0 to rebuilt data and corresponds
    to the last known value.
    """
    if(diff_order==0):
        return np.array(predictions)
    elif(diff_order==1):
        return_preds = []
        return_preds.append(last_value)
        for i in range(len(predictions)):
            return_preds.append(predictions[i] + return_preds[i])

        return np.array(return_preds)
    elif(diff_order=='return-price'):
        return_preds = []
        return_preds.append(last_value)
        for i in range(len(predictions)):
            return_preds.append(predictions[i] * return_preds[i] + return_preds[i])

        return return_preds

        # return np.array(return_preds)
        # predictions[0] = predictions[0] * last_value + last_value
        # for i in range(1, len(predictions)):
        #     predictions[i] = predictions[i] * predictions[i-1] + predictions[i-1]
        # return np.array(predictions)



def insert_predictions(data, predictions, startAt, stopAt, diff_order=0):
    '''
    Adds the predicted values to the data DataFrame and cancels the diffenrentiation.
    '''

    if(stopAt==0):
        stopAt = len(data)

    data['Predictions'] = 0.0
    data['Predictions'].values[startAt:stopAt] = inv_differenciate(predictions, diff_order, data['Close'][startAt-1])

        #data['Predictions'].values[len(data)-len(predictions):] = predictions
        #data['Predictions'] = data['Predictions'] * data['Predictions'].shift(periods=1)
        #data['Predictions'] = data['Predictions'].cumsum() + data['Close'][startAt]

    #print(data['Predictions'].describe())

    return data


def plot_predictions(data, predictions, startAt, stopAt=0, diff_order=0, print_rms=False):
    '''
    Plots the known data in a color, the predicted data in a second color
    and if it exists the valid data assiciated to the predictions in a thrid one
    '''

    data = insert_predictions(data, predictions, startAt, stopAt, diff_order)

    if(stopAt==0):
        stopAt = len(data)

    plt.plot(data['Close'][:startAt])
    if(data['Close'][startAt:stopAt].isnull().any()):
        plt.plot(data['Predictions'][startAt:stopAt])
    else:
        plt.plot(data[['Close', 'Predictions']][startAt:stopAt])

    if(print_rms):
        rms = calculate_rms(data['Close'][startAt:stopAt], data['Predictions'][startAt:stopAt])
        plt.suptitle('RMS = ' + str(rms))
    plt.show()


def calculate_rms(a, b):
    '''
    Caclulate the root mean square between two lists a and b
    '''

    rms = np.sqrt(np.mean(np.power((np.array(a)-np.array(b)),2)))

    return rms


def moving_average(data, startAt, stopAt=0):
    '''
    Applies the moving average to data to predict points whose index is
    between startAt and stopAt.
    If stopAt is not provided, default value is the lenght of data.
    If do_rms is set to True, prints the rms between the predicted values and
    the known values.
    '''

    if(stopAt==0):
        stopAt = len(data)

    train = data[:startAt]
    valid = data[startAt:stopAt]

    periods = stopAt - startAt

    predictions = []
    for i in range(0, periods):
        a = train['Close'][startAt - periods + i:].sum() + sum(predictions)
        b = a/periods
        predictions.append(b)

    return predictions


def linear_regression(data, startAt, stopAt=0):
    '''
    Applies the linear regression method to data to predict points whose index is
    between startAt and stopAt.
    If stopAt is not provided, default value is the lenght of data.
    If do_rms is set to True, prints the rms between the predicted values and
    the known values.
    '''

    data_copy = data.copy()

    if(stopAt==0):
        stopAt = len(data_copy)

    periods = stopAt - startAt

    from fastai.tabular import add_datepart
    add_datepart(data_copy, 'Date')
    data_copy.drop('Elapsed', axis=1, inplace=True)

    # setting importance of days before and after weekends
    # we assume that fridays and mondays are more important
    # 0 is Monday, 1 is Tuesday...
    data_copy['mon_fri'] = 0
    data_copy['mon_fri'].mask(data_copy['Dayofweek'].isin([0,4]), 1, inplace=True)
    data_copy['mon_fri'].where(data_copy['Dayofweek'].isin([0,4]), 0, inplace=True)

    train = data_copy[:startAt]
    valid = data_copy[startAt:stopAt]

    x_train = train.drop('Close', axis=1)
    y_train = train['Close']
    x_valid = valid.drop('Close', axis=1)
    y_valid = valid['Close']

    from sklearn.linear_model import LinearRegression
    model = LinearRegression()
    model.fit(x_train,y_train) # calculating coefficients

    predictions = model.predict(x_valid) # Applies the regression

    return predictions


def knn(data, startAt, stopAt=0):
    '''
    Classifies the point between startAt and stopAt with the k-nearest
    neighbors method. Automaticaly finds the best number of neighbors.
    If stopAt is not provided, default value is the lenght of data.
    If do_rms is set to True, prints the rms between the predicted values and
    the known values.
    '''

    data_copy = data.copy()

    if(stopAt==0):
        stopAt = len(data_copy)

    periods = stopAt - startAt

    from fastai.tabular import add_datepart
    add_datepart(data_copy, 'Date')
    data_copy.drop('Elapsed', axis=1, inplace=True)

    # setting importance of days before and after weekends
    # we assume that fridays and mondays are more important
    # 0 is Monday, 1 is Tuesday...
    data_copy['mon_fri'] = 0
    data_copy['mon_fri'].mask(data_copy['Dayofweek'].isin([0,4]), 1, inplace=True)
    data_copy['mon_fri'].where(data_copy['Dayofweek'].isin([0,4]), 0, inplace=True)

    train = data_copy[:startAt]
    valid = data_copy[startAt:stopAt]

    from sklearn import neighbors
    from sklearn.model_selection import GridSearchCV
    from sklearn.preprocessing import MinMaxScaler
    scaler = MinMaxScaler(feature_range=(0, 1))

    x_train_scaled = scaler.fit_transform(train.drop('Close', axis=1))
    x_train = pd.DataFrame(x_train_scaled)
    y_train = train['Close']

    x_valid_scaled = scaler.fit_transform(valid.drop('Close', axis=1))
    x_valid = pd.DataFrame(x_valid_scaled)
    y_valid = valid['Close']

    params = {'n_neighbors':[2,3,4,5,6,7,8,9]}
    knn = neighbors.KNeighborsRegressor()
    model = GridSearchCV(knn, params, cv=5)

    model.fit(x_train,y_train)
    predictions = model.predict(x_valid)

    return predictions


def arima_auto(data, startAt, stopAt=0):
    '''
    Applies the moving average to data to predict points whose index is
    between startAt and stopAt.
    If stopAt is not provided, default value is the lenght of data.
    If do_rms is set to True, prints the rms between the predicted values and
    the known values.
    '''

    if(stopAt==0):
        stopAt = len(data)

    periods = stopAt - startAt

    train = data[:startAt]
    valid = data[startAt:stopAt]

    training = train['Close']
    validation = valid['Close']

    from pmdarima.arima import auto_arima
    model = auto_arima(training, start_p=1, start_q=1,max_p=3, max_q=3, m=12,start_P=0, seasonal=True,d=1, D=1, trace=True,error_action='ignore',suppress_warnings=True)
    # searches for the best parameters
    model.fit(training)

    predictions = model.predict(n_periods=periods)

    return predictions


def prophet(data, startAt, stopAt=0, do_rms=False):
    '''
    Applies the Prophet algorithm to data to predict points whose index is
    between startAt and stopAt.
    If stopAt is not provided, default value is the lenght of data.
    If do_rms is set to True, prints the rms between the predicted values and
    the known values.
    '''

    data_copy = data.copy()

    if(stopAt==0):
        stopAt = len(data)

    periods = stopAt - startAt

    from fbprophet import Prophet

    data_copy.rename(columns={'Close': 'y', 'Date': 'ds'}, inplace=True)
    train = data_copy[:startAt]
    valid = data_copy[startAt:stopAt]

    model = Prophet(daily_seasonality=True)
    model.fit(train)
    close_prices = model.make_future_dataframe(periods=len(valid))
    forecast = model.predict(close_prices)

    predictions = forecast['yhat'][startAt:stopAt]

    if(do_rms):
        rms = calculate_rms(valid['y'], predictions)
        print(rms)

    return predictions


def svm(data, startAt, stopAt=0):
    '''

    '''

    data_copy = data.copy()

    if(stopAt==0):
        stopAt = len(data_copy)

    periods = stopAt - startAt

    from fastai.tabular import add_datepart
    add_datepart(data_copy, 'Date')
    data_copy.drop('Elapsed', axis=1, inplace=True)

    # setting importance of days before and after weekends
    # we assume that fridays and mondays are more important
    # 0 is Monday, 1 is Tuesday...
    data_copy['mon_fri'] = 0
    data_copy['mon_fri'].mask(data_copy['Dayofweek'].isin([0,4]), 1, inplace=True)
    data_copy['mon_fri'].where(data_copy['Dayofweek'].isin([0,4]), 0, inplace=True)

    train = data_copy[:startAt]
    valid = data_copy[startAt:stopAt]

    x_train = train.drop('Close', axis=1)
    y_train = train['Close']
    x_valid = valid.drop('Close', axis=1)
    y_valid = valid['Close']

    from sklearn import svm
    model = svm.SVR(gamma='scale', kernel='linear', degree=2, coef0=1)
    model.fit(x_train, y_train)

    predictions = model.predict(x_valid)

    return predictions


def MLPRegression(data, startAt, stopAt=0, **kwargs):
    '''

    '''

    data_copy = data.copy()

    if(stopAt==0):
        stopAt = len(data_copy)

    periods = stopAt - startAt

    from fastai.tabular import add_datepart
    add_datepart(data_copy, 'Date')
    data_copy.drop('Elapsed', axis=1, inplace=True)

    # setting importance of days before and after weekends
    # we assume that fridays and mondays are more important
    # 0 is Monday, 1 is Tuesday...
    data_copy['mon_fri'] = 0
    data_copy['mon_fri'].mask(data_copy['Dayofweek'].isin([0,4]), 1, inplace=True)
    data_copy['mon_fri'].where(data_copy['Dayofweek'].isin([0,4]), 0, inplace=True)

    train = data_copy[:startAt]
    valid = data_copy[startAt:stopAt]

    x_train = train.drop('Close', axis=1)
    y_train = train['Close']
    x_valid = valid.drop('Close', axis=1)
    y_valid = valid['Close']

    from sklearn.neural_network import MLPRegressor
    model = MLPRegressor(**kwargs)
    model.fit(x_train, y_train)

    predictions = model.predict(x_valid)

    return predictions


def theta_method(data, startAt, stopAt=None, theta=0, alpha=0.5):
    if stopAt is None:
        stopAt = len(data)

    if (theta!=0):
        raise ArithmeticError('theta value must be 0')

    if (alpha <= 0) or (alpha >= 1):
        raise ArithmeticError('alpha value must be in ]0;1[')

    #data_copy = data.copy()
    train = data[:startAt]
    valid = data[startAt:stopAt]
    predictions = []
    n = len(train)

    sum_for_b_hat = sum(i*train['Close'][i] for i in range(train.first_valid_index(), len(train)))

    b_hat = lambda theta : 6 * (1-theta) / (n**2 - 1) * (2/n * sum_for_b_hat - (n+1) * np.mean(train['Close']))
    a_hat = lambda theta : (1-theta) * np.mean(train['Close']) - b_hat(theta) * (n-1)/2
    y = lambda theta : [a_hat(theta) + b_hat(theta) * (t-theta) + theta * train['Close'][t] for t in range(train.first_valid_index(), len(train))]

    y_hat_0 = lambda theta, h : a_hat(theta) + b_hat(theta) * (n + h - 1)

    y_2 = y(2-theta) # Y_(2-theta)

    y_hat_2 = lambda theta, h : alpha * sum((1-alpha)**i * y_2[n-i-1] for i in range(train.first_valid_index(), n)) + (1-alpha)**n * y_2[0]

    x_hat = lambda theta, h : 1/2 * (y_hat_0(theta, h) + y_hat_2(theta, h))
#    train = train.append({'Close': x_hat(h)}, ignore_index=True)
    predictions = [x_hat(theta, h) for h in range(stopAt - startAt)]

#    for j in range(startAt, stopAt):
#        sum_for_b_hat = sum_for_b_hat + j*train['Close'][j]
#
#        #y_hat_0 = lambda h : a_hat(0) + b_hat(0) * (len(train) + h - 1)
#
#        y_2 = y(2)
#        #y_hat_2 = lambda h : alpha * sum((1-alpha)**i * y_2[len(train)-i-1] for i in range(len(train))) + (1-alpha)**len(train) * y_2[0]
#        train = train.append({'Close': x_hat(h)}, ignore_index=True)
#        predictions.append(x_hat(h))

    return predictions


def theta_method_2(data, startAt, stopAt=None, theta=0, alpha=0.5):
    raise NotImplementedError("This function is not available")
    if stopAt is None:
        stopAt = len(data)

    if theta!=0:
        raise ArithmeticError('theta value must be 0')
    elif alpha <= 0 or alpha >= 1:
        raise ArithmeticError('alpha value must be in ]0;1[')

    data_copy = data.copy()
    train = data_copy[:startAt]
    predictions = []
    n = len(train)

    h = 1

    sum_for_b_hat = sum(i*train['Close'][i] for i in range(train.first_valid_index(),len(train)))

    b_hat = lambda theta : 6 * (1-theta) / (n**2 - 1) * (2/n * sum_for_b_hat - (n+1) * np.mean(train['Close']))
    a_hat = lambda theta : (1-theta) * np.mean(train['Close']) - b_hat(theta) * (n-1)/2
    y = lambda theta : [a_hat(theta) + b_hat(theta) * (t-theta) + theta * train['Close'][t] for t in range(train.first_valid_index(),len(train))]

    y_hat_0 = lambda theta, h : a_hat(theta) + b_hat(theta) * (n + h - 1)

    y_2 = y(2-theta) # Y_(2-theta)

    y_hat_2 = lambda theta, h : alpha * sum((1-alpha)**i * y_2[n-i-1] for i in range(train.first_valid_index(), n)) + (1-alpha)**n * y_2[0]

    x_hat = 1/2 * (y_hat_0(theta, h) + y_hat_2(theta, h))
    train = train.append({'Close': x_hat}, ignore_index=True)
    #predictions = [x_hat(theta, h) for h in range(stopAt - startAt)]
    predictions.append(x_hat)

    for j in range(startAt, stsopAt):
        sum_for_b_hat = sum_for_b_hat + j*train['Close'][j]
        b_hat = lambda theta : 6 * (1-theta) / (j**2 - 1) * (2/j * sum_for_b_hat - (j+1) * np.mean(train['Close']))
        a_hat = lambda theta : (1-theta) * np.mean(train['Close']) - b_hat(theta) * (j-1)/2

        y_hat_0 = lambda theta, h : a_hat(theta) + b_hat(theta) * (j + h - 1)

        y_2 = y(2-theta)
        y_hat_2 = lambda theta, h : alpha * sum((1-alpha)**i * y_2[j-i-1] for i in range(train.first_valid_index(), j)) + (1-alpha)**j * y_2[0]

        x_hat = 1/2 * (y_hat_0(theta, h) + y_hat_2(theta, h))
        train = train.append({'Close': x_hat}, ignore_index=True)
        predictions.append(x_hat)

    return predictions


def max_profit(data, buy_time, method, periods, **kwargs):
    """
    On donne les données ‘data’, temps d'achat ‘buy_time’ sous forme
    de chaine de caractère, on donne la méthode de prédiction ‘method’ qui est
    une des fonctions ci-dessus et le nombre de points à prédire ‘periods’.
    **kwrags correspond aux paramètres supplémentaires de certaines fonctions
    de prédiction.

    A faire : se débrouiller pour prédire les points à partir de
    data['Close'][:startAt] comme données d'entrainement, on n'aura pas de
    données de validation. Ensuite chercher simplement le max entre les indices
    startAt et startAt + periods.

    En fonction de l'indice de differentiation choisi, utiliser la fonction
    inv_differenciate pour que le tableau ‘predictions’ soit utilisable.
    """
    startAt = data.index[data['Date'] == buy_time][0] # on cherche l'indice correspondant à la date
    predictions = method(data, startAt, periods, **kwargs)


    return predictions
